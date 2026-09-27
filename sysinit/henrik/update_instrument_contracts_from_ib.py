"""
通过 IB 定向更新某个品种指定月份之后的合约价格（本地新增脚本，非上游内容）。

为什么需要：
    上游 `sysproduction.update_historical_prices` 只能按“采样合约表”逐品种全量更新，
    无法指定合约月份；而修换月时需要把前端/次月合约的历史补出来（换月日要两个合约同时有价）。
    本脚本直接调用上游的 `update_historical_prices_for_instrument_and_contract`，
    逐合约拉取 intraday + daily 并合并写入 parquet 价格库，默认 dry-run 不写数据。

前置条件：
    IB Gateway / TWS 已启动并登录（private_config.yaml 里的 ib_ipaddress:ib_port）。

用法：
    # 只列出会更新哪些合约、当前数据情况（不写库）
    python sysinit/henrik/update_instrument_contracts_from_ib.py --instrument VIX --from-contract 20260100

    # 真正更新
    python sysinit/henrik/update_instrument_contracts_from_ib.py --instrument VIX --from-contract 20260100 --commit

    # 只看重叠情况
    python sysinit/henrik/update_instrument_contracts_from_ib.py --instrument VIX --from-contract 20260700 --overlap-only

    # 历史回填（把 IB 能给到的更早数据补进来，用于制造相邻合约重叠）
    # 注意：只对仍在交易的合约使用；已到期合约 IB 可能解析到周合约，不要回填
    python sysinit/henrik/update_instrument_contracts_from_ib.py --instrument VIX --from-contract 20261000 --backfill --commit
"""
import argparse

import pandas as pd

from syscore.dateutils import DAILY_PRICE_FREQ, Frequency
from syscore.pandas.frequency import merge_data_with_different_freq
from sysdata.data_blob import dataBlob
from sysdata.tools.cleaner import get_config_for_price_filtering

from sysobjects.futures_per_contract_prices import futuresContractPrices

from sysproduction.data.broker import dataBroker
from sysproduction.data.contracts import dataContracts
from sysproduction.data.prices import diagPrices, updatePrices
from sysproduction.update_historical_prices import (
    update_historical_prices_for_instrument_and_contract,
)


def get_contract_objects(instrument_code: str, from_contract: str) -> list:
    diag_contracts = dataContracts()
    all_contracts = diag_contracts.get_all_contract_objects_for_instrument_code(
        instrument_code
    )
    selected = [c for c in all_contracts if str(c.date_str) >= str(from_contract)]
    return sorted(selected, key=lambda c: str(c.date_str))


def contract_price_summary(instrument_code: str, contract_object) -> dict:
    """从价格库读回该合约的数据情况（不依赖 IB）。"""
    diag_prices = diagPrices()
    try:
        prices = diag_prices.get_merged_prices_for_contract_object(contract_object)
    except Exception as e:
        return {"contract": str(contract_object.date_str), "rows": 0, "note": str(e)}

    if prices is None or len(prices) == 0:
        return {"contract": str(contract_object.date_str), "rows": 0}

    index = pd.DatetimeIndex(prices.index)
    return {
        "contract": str(contract_object.date_str),
        "rows": len(prices),
        "first": str(index.min()),
        "last": str(index.max()),
        "last_price": float(prices["FINAL"].iloc[-1]) if "FINAL" in prices else None,
    }


def report_overlaps(summaries: list) -> None:
    """连续合约之间是否有重叠交易日：没有重叠的话换月无法落位。"""
    print("\n合约相邻重叠检查（换月落位需要相邻合约有共同交易日）：")
    for previous, current in zip(summaries, summaries[1:]):
        if not previous.get("last") or not current.get("first"):
            print(f"  {previous['contract']} -> {current['contract']}: 数据不全，跳过")
            continue
        prev_last = pd.Timestamp(previous["last"]).normalize()
        cur_first = pd.Timestamp(current["first"]).normalize()
        if cur_first <= prev_last:
            print(
                f"  {previous['contract']} -> {current['contract']}: 重叠，"
                f"{cur_first.date()} ~ {prev_last.date()}"
            )
        else:
            print(
                f"  {previous['contract']} -> {current['contract']}: **无重叠**"
                f"（前合约止于 {prev_last.date()}，后合约起于 {cur_first.date()}）"
            )


def _union_prices(*price_frames) -> futuresContractPrices:
    """合并多份价格序列：并集，重复时间戳保留先出现的（既有数据优先）。"""
    frames = [pd.DataFrame(p) for p in price_frames if p is not None and len(p) > 0]
    if not frames:
        return futuresContractPrices(pd.DataFrame())
    combined = pd.concat(frames)
    combined = combined[~combined.index.duplicated(keep="first")].sort_index()
    return futuresContractPrices(combined)


def backfill_contract_from_ib(data, contract_object, instrument_code: str) -> dict:
    """
    历史回填：把 IB 返回的更早数据与既有数据取并集后整份写回。

    上游 `update_prices_at_frequency_for_contract` 只接受比库里最后一行更新的数据
    （`merge_newer_data`），历史缺口补不进来，所以这里用 overwrite 的写法。
    """
    diag_prices = diagPrices(data)
    price_updater = updatePrices(data)
    broker = dataBroker(data)

    existing_hour = diag_prices.get_prices_at_frequency_for_contract_object(
        contract_object, frequency=Frequency.Hour
    )
    existing_day = diag_prices.get_prices_at_frequency_for_contract_object(
        contract_object, frequency=DAILY_PRICE_FREQ
    )
    existing_mixed = diag_prices.get_merged_prices_for_contract_object(contract_object)

    ib_hour = broker.get_prices_at_frequency_for_contract_object(
        contract_object, Frequency.Hour
    )
    ib_day = broker.get_prices_at_frequency_for_contract_object(
        contract_object, DAILY_PRICE_FREQ
    )

    merged_hour = _union_prices(existing_hour, ib_hour)
    merged_day = _union_prices(existing_day, ib_day)
    merged_mixed = _union_prices(existing_mixed, ib_hour, ib_day)

    price_updater.overwrite_prices_at_frequency_for_contract(
        contract_object=contract_object, new_prices=merged_hour, frequency=Frequency.Hour
    )
    price_updater.overwrite_prices_at_frequency_for_contract(
        contract_object=contract_object,
        new_prices=merged_day,
        frequency=DAILY_PRICE_FREQ,
    )
    price_updater.overwrite_merged_prices_for_contract(
        contract_object=contract_object, new_prices=merged_mixed
    )

    # 与上游 write_merged_prices_for_contract 的校验口径保持一致
    check = merge_data_with_different_freq([merged_hour, merged_day])
    return {
        "contract": str(contract_object.date_str),
        "existing_mixed": len(existing_mixed),
        "ib_hour": len(ib_hour),
        "ib_day": len(ib_day),
        "merged_mixed": len(merged_mixed),
        "merged_from_freq": len(check),
    }


def main():
    parser = argparse.ArgumentParser(description="通过 IB 定向更新合约价格")
    parser.add_argument("--instrument", required=True, help="品种代码，例如 VIX")
    parser.add_argument(
        "--from-contract",
        default="20260100",
        help="起始合约月份（含），格式 YYYYMM00，默认 20260100",
    )
    parser.add_argument("--commit", action="store_true", help="真正写入价格库（默认 dry-run）")
    parser.add_argument("--overlap-only", action="store_true", help="只打印重叠检查")
    parser.add_argument(
        "--backfill",
        action="store_true",
        help="历史回填模式：把 IB 的更早数据也并进来（默认只做增量追加）",
    )
    args = parser.parse_args()

    with dataBlob(log_name="Update-Instrument-Contracts-From-IB") as data:
        contracts = get_contract_objects(args.instrument, args.from_contract)
        if not contracts:
            print(
                f"{args.instrument} 在合约表里没有 {args.from_contract} 之后的合约记录"
            )
            return 1

        before = [contract_price_summary(args.instrument, c) for c in contracts]
        print(f"\n{args.instrument} 目标合约 {args.from_contract} 起，共 {len(contracts)} 个")
        print(f"{'合约':<10}{'现有行数':>8}{'首个时间':>22}{'最后时间':>22}")
        for row in before:
            print(
                f"{row['contract']:<10}{row.get('rows', 0):>8}"
                f"{row.get('first', '-'):>22}{row.get('last', '-'):>22}"
            )

        if args.overlap_only:
            report_overlaps(before)
            return 0

        if args.backfill and not args.commit:
            print("\n[backfill 预览] 只向 IB 查询、不写库：")
            broker = dataBroker(data)
            diag_prices = diagPrices(data)
            for contract_object in contracts:
                try:
                    ib_hour = broker.get_prices_at_frequency_for_contract_object(
                        contract_object, Frequency.Hour
                    )
                    ib_day = broker.get_prices_at_frequency_for_contract_object(
                        contract_object, DAILY_PRICE_FREQ
                    )
                    existing = diag_prices.get_merged_prices_for_contract_object(
                        contract_object
                    )
                    print(
                        f"  {contract_object.date_str}: 库内 {len(existing)} 行 / "
                        f"IB 小时 {len(ib_hour)} 行（{ib_hour.index.min() if len(ib_hour) else '-'}） / "
                        f"IB 日线 {len(ib_day)} 行"
                    )
                except Exception as e:
                    print(f"  {contract_object.date_str}: 失败 {type(e).__name__}: {e}")
            print("\n[backfill 预览结束] 确认后加 --commit 执行。")
            return 0

        if not args.commit:
            print("\n[dry-run] 未写入任何数据；确认无误后加 --commit 执行。")
            report_overlaps(before)
            return 0

        if args.backfill:
            print("\n开始历史回填（IB 数据与既有数据取并集后整份写回）……")
            results = []
            for contract_object in contracts:
                print(f"  -> {args.instrument}/{contract_object.date_str}")
                try:
                    results.append(
                        backfill_contract_from_ib(data, contract_object, args.instrument)
                    )
                except Exception as e:
                    print(f"     失败：{type(e).__name__}: {e}")
            print(
                f"\n{'合约':<10}{'原行数':>8}{'IB小时':>8}{'IB日线':>8}"
                f"{'并集行数':>10}{'频率合并':>10}"
            )
            for row in results:
                print(
                    f"{row['contract']:<10}{row['existing_mixed']:>8}{row['ib_hour']:>8}"
                    f"{row['ib_day']:>8}{row['merged_mixed']:>10}{row['merged_from_freq']:>10}"
                )
            report_overlaps(
                [contract_price_summary(args.instrument, c) for c in contracts]
            )
            return 0

        cleaning_config = get_config_for_price_filtering(data)
        print("\n开始通过 IB 更新（hourly + daily）……")
        for contract_object in contracts:
            print(f"  -> {args.instrument}/{contract_object.date_str}")
            try:
                update_historical_prices_for_instrument_and_contract(
                    contract_object,
                    data,
                    cleaning_config=cleaning_config,
                    interactive_mode=False,
                )
            except Exception as e:
                print(f"     失败：{type(e).__name__}: {e}")

        after = [contract_price_summary(args.instrument, c) for c in contracts]
        print(f"\n更新后：{'合约':<10}{'行数':>8}{'首个时间':>22}{'最后时间':>22}")
        for row in after:
            print(
                f"{row['contract']:<10}{row.get('rows', 0):>8}"
                f"{row.get('first', '-'):>22}{row.get('last', '-'):>22}"
            )
        report_overlaps(after)
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
