"""
方案 2：不动分频文件，直接把 IB 增量合并进「合并文件」。

背景（FIR-127）：
    价格库当前基线是 Norgate 导入的合并文件（≤2026-09-18，时间戳 00:00），没有 Day@ / Hour@。
    上游 `write_merged_prices_for_contract` 是用分频文件**重建**合并文件，在没有分频文件时
    会把合并文件里的历史整体丢掉（FIR-137 的事故）；而带尖峰检查的增量写入又会因为
    「读不到旧数据 → 整段新数据都被检查」把低波动品种的正常波动判成尖峰。

本脚本按方案 2 处理：
    1. 读**合并文件**里的旧数据（即接受 ≤09-18 的 Norgate 结果，不做任何改写）；
    2. 从 IB 取该合约的日线 + 小时线（只做常规清洗，不做尖峰判定）；
    3. 用 add_rows_to_existing_data(check_for_spike=False) 只追加比旧数据更新的行；
    4. 覆盖写回合并文件（分频文件不创建、不改动）。

默认 dry-run，不写任何数据。用法：
    python sysinit/henrik/update_merged_prices_from_ib.py                    # 只统计
    python sysinit/henrik/update_merged_prices_from_ib.py --commit           # 全品种写入
    python sysinit/henrik/update_merged_prices_from_ib.py --commit --instruments CORN GOLD
    python sysinit/henrik/update_merged_prices_from_ib.py --limit 5 --commit
"""

import argparse
import sys

import pandas as pd

from syscore.dateutils import DAILY_PRICE_FREQ
from syscore.pandas.frequency import merge_data_with_different_freq
from sysdata.data_blob import dataBlob
from sysobjects.contracts import futuresContract
from sysobjects.futures_per_contract_prices import futuresContractPrices
from sysproduction.data.broker import dataBroker
from sysproduction.data.contracts import dataContracts
from sysproduction.data.prices import diagPrices, updatePrices


def update_contract(data, contract_object, commit: bool) -> dict:
    result = dict(
        contract=str(contract_object.key),
        old_rows=0,
        old_last="",
        new_rows=0,
        new_last="",
        added=0,
        status="",
    )

    diag = diagPrices(data)
    broker = dataBroker(data)
    price_updater = updatePrices(data)
    price_data = diag.db_futures_contract_price_data

    try:
        old_prices = price_data.get_merged_prices_for_contract_object(contract_object)
    except Exception as error:
        result["status"] = "旧数据读取失败: %s" % type(error).__name__
        return result

    result["old_rows"] = len(old_prices)
    if len(old_prices) > 0:
        result["old_last"] = str(pd.DatetimeIndex(old_prices.index)[-1])

    intraday_frequency = diag.get_intraday_frequency_for_historical_download()
    list_of_new_data = []
    for frequency in [intraday_frequency, DAILY_PRICE_FREQ]:
        try:
            prices = broker.get_cleaned_prices_at_frequency_for_contract_object(
                contract_object=contract_object, frequency=frequency
            )
        except Exception:
            continue
        if prices is not None and len(prices) > 0:
            list_of_new_data.append(prices)

    if not list_of_new_data:
        result["status"] = "IB 无数据"
        return result

    new_prices = merge_data_with_different_freq(list_of_new_data)
    result["new_rows"] = len(new_prices)
    result["new_last"] = str(pd.DatetimeIndex(new_prices.index)[-1])

    if len(old_prices) == 0:
        merged = new_prices
    else:
        # 只追加比旧数据更新的行；不做尖峰判定（本方案的取舍：接受 IB 增量）
        merged = old_prices.add_rows_to_existing_data(
            new_prices, check_for_spike=False
        )

    result["added"] = len(merged) - len(old_prices)
    if result["added"] <= 0:
        result["status"] = "无新增"
        return result

    if commit:
        price_updater.overwrite_merged_prices_for_contract(
            contract_object=contract_object,
            new_prices=futuresContractPrices(merged),
        )
        result["status"] = "已写入 +%d 行" % result["added"]
    else:
        result["status"] = "[dry-run] 将写入 +%d 行" % result["added"]

    return result


def update_instrument(data, instrument_code: str, commit: bool) -> dict:
    diag_contracts = dataContracts(data)
    all_contracts = diag_contracts.get_all_contract_objects_for_instrument_code(
        instrument_code
    )
    contract_list = all_contracts.currently_sampling()

    summary = dict(instrument=instrument_code, contracts=len(contract_list), added=0, detail=[])
    for contract_object in contract_list:
        result = update_contract(data, contract_object, commit=commit)
        summary["added"] += max(result["added"], 0)
        summary["detail"].append(result)

    return summary


def front_contracts_from_multiple_prices(instrument_code: str) -> list:
    """从已入库的 multiple prices 末行取前端/次月/携带合约，用于采样表没覆盖前端的品种。"""
    diag = diagPrices()
    try:
        multiple_prices = diag.db_futures_multiple_prices_data.get_multiple_prices(
            instrument_code
        )
    except Exception:
        return []
    if len(multiple_prices) == 0:
        return []

    last_row = multiple_prices.iloc[-1]
    contracts = []
    for column in ["PRICE_CONTRACT", "FORWARD_CONTRACT", "CARRY_CONTRACT"]:
        contract_str = str(last_row[column])
        if contract_str not in contracts and contract_str != "nan":
            contracts.append(contract_str)
    return contracts


def update_instrument_front_contracts(data, instrument_code: str, commit: bool) -> dict:
    contract_ids = front_contracts_from_multiple_prices(instrument_code)
    summary = dict(
        instrument=instrument_code,
        contracts=len(contract_ids),
        added=0,
        detail=[],
    )
    for contract_id in contract_ids:
        contract_object = futuresContract(instrument_code, contract_id)
        result = update_contract(data, contract_object, commit=commit)
        summary["added"] += max(result["added"], 0)
        summary["detail"].append(result)
    return summary


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="方案 2：把 IB 增量合并进合并文件")
    parser.add_argument("--commit", action="store_true", help="真正写库（默认 dry-run）")
    parser.add_argument("--instruments", nargs="*", default=None)
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--verbose", action="store_true")
    parser.add_argument(
        "--use-front-contracts",
        action="store_true",
        help="不看采样表，直接按 multiple prices 末行的前端/次月/携带合约更新"
        "（用于采样表没覆盖前端的品种）",
    )
    parser.add_argument(
        "--contracts",
        nargs="*",
        default=None,
        help="直接指定合约，格式 INSTRUMENT#YYYYMM00（配合 --instruments 使用；优先于其它模式）",
    )
    args = parser.parse_args(argv)

    with dataBlob(log_name="Update-Merged-Prices-From-IB") as data:
        diag = diagPrices(data)
        instruments = diag.get_list_of_instruments_in_multiple_prices()
        instruments = sorted(instruments)
        if args.instruments:
            wanted = {code.upper() for code in args.instruments}
            instruments = [c for c in instruments if c.upper() in wanted]
        if args.limit:
            instruments = instruments[: args.limit]

        print(
            "%s：%d 个品种（%s）"
            % (
                "[commit]" if args.commit else "[dry-run]",
                len(instruments),
                "指定合约清单"
                if args.contracts
                else (
                    "按 multiple prices 前端合约"
                    if args.use_front_contracts
                    else "只处理采样合约"
                ),
            ),
            flush=True,
        )

        explicit_contracts = {}
        for spec in args.contracts or []:
            if "#" not in spec:
                print("忽略无法识别的合约参数: %s" % spec)
                continue
            instrument_code, contract_id = spec.split("#", 1)
            explicit_contracts.setdefault(instrument_code.upper(), []).append(contract_id)
        if explicit_contracts:
            instruments = sorted(explicit_contracts.keys())

        total_added = 0
        failures = []
        for position, instrument_code in enumerate(instruments, start=1):
            try:
                if explicit_contracts.get(instrument_code.upper()):
                    summary = dict(
                        instrument=instrument_code,
                        contracts=len(explicit_contracts[instrument_code.upper()]),
                        added=0,
                        detail=[],
                    )
                    for contract_id in explicit_contracts[instrument_code.upper()]:
                        result = update_contract(
                            data,
                            futuresContract(instrument_code, contract_id),
                            commit=args.commit,
                        )
                        summary["added"] += max(result["added"], 0)
                        summary["detail"].append(result)
                elif args.use_front_contracts:
                    summary = update_instrument_front_contracts(
                        data, instrument_code, commit=args.commit
                    )
                else:
                    summary = update_instrument(data, instrument_code, commit=args.commit)
            except Exception as error:
                failures.append((instrument_code, "%s: %s" % (type(error).__name__, str(error)[:80])))
                continue
            total_added += summary["added"]
            detail = ", ".join(
                "%s+%d" % (row["contract"], row["added"])
                for row in summary["detail"]
                if row["added"] > 0
            )
            print(
                "  [%3d/%3d] %-16s 合约 %d  新增 %d 行  %s"
                % (position, len(instruments), instrument_code, summary["contracts"], summary["added"], detail),
                flush=True,
            )
            if args.verbose:
                for row in summary["detail"]:
                    print(
                        "        %s old=%d(%s) new=%d(%s) %s"
                        % (row["contract"], row["old_rows"], row["old_last"], row["new_rows"], row["new_last"], row["status"])
                    )

        print("\n合计新增 %d 行" % total_added)
        if failures:
            print("失败 %d 个品种：" % len(failures))
            for code, message in failures[:20]:
                print("  %s: %s" % (code, message))
        if not args.commit:
            print("（dry-run，没有写任何数据；确认后加 --commit）")

    return 0


if __name__ == "__main__":
    sys.exit(main())
