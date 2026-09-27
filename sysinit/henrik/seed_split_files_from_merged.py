"""
把「合并文件」里的历史价格拆成 Day@ / Hour@ 分频文件（FIR-127 第 A 步）。

⚠️ 一次性脚本：**已于 2026-09-27 执行完毕**，不要重复运行
   （脚本本身是 ignore_duplication=False，重复跑只会告警不覆盖，但没必要）。

为什么需要：
    Norgate 导入只写合并文件（INSTRUMENT#YYYYMM00.parquet），没有 Day@ / Hour@。
    IB 每日增量在写库前会读「按频率」的旧数据来判断尖峰；读不到旧数据时 PST 会把
    整段新数据都当作要检查（NEW_DATA_ONLY），于是低波动品种的正常波动也会被判成尖峰
    （FIR-127 的 154 次拒绝就是这么来的），同时也不利于 FIR-137 的「合并文件历史被覆盖」。

拆分口径（已确认）：价格库当前基线是 Norgate 导出的日线，时间戳是当日 **00:00**；
    仓库自带的 create_hourly_and_daily.py 只认 23:00，直接用会把日线当小时线。
    本脚本按「同一日期优先取 00:00 的行、没有 00:00 才取 23:00 的行」判日线，其余判小时线。

写入语义：调用 PST 的 write_prices_at_frequency_for_contract_object(ignore_duplication=False)，
    已存在分频文件时只告警、不覆盖，避免冲掉 09-24 那批 IB 分频数据。

用法：
    python sysinit/henrik/seed_split_files_from_merged.py --dry-run
    python sysinit/henrik/seed_split_files_from_merged.py --commit
    python sysinit/henrik/seed_split_files_from_merged.py --commit --instruments CORN SP500
"""

import argparse
import sys

import pandas as pd

from syscore.dateutils import DAILY_PRICE_FREQ, HOURLY_FREQ
from sysobjects.futures_per_contract_prices import futuresContractPrices
from sysproduction.data.prices import diagPrices

MIDNIGHT_OFFSET = pd.Timedelta(hours=0)
NOTIONAL_CLOSE_OFFSET = pd.Timedelta(hours=23)


def split_merged_prices(merged: pd.DataFrame) -> tuple:
    """返回 (daily_rows, hourly_rows)。同一天优先取 00:00 的行（Norgate 基线）。"""
    frame = pd.DataFrame(merged)
    if len(frame) == 0:
        return frame, frame

    index = pd.DatetimeIndex(frame.index)
    midnight = index == index.normalize() + MIDNIGHT_OFFSET
    notional_close = index == index.normalize() + NOTIONAL_CLOSE_OFFSET
    midnight_dates = set(index[midnight].normalize())
    daily_mask = midnight | (notional_close & ~index.normalize().isin(midnight_dates))

    daily = frame[daily_mask]
    hourly = frame[~daily_mask]
    return daily, hourly


def seed_instrument(instrument_code: str, commit: bool, quiet: bool = False) -> dict:
    diag = diagPrices()
    price_data = diag.db_futures_contract_price_data
    contracts = price_data.contracts_with_merged_price_data_for_instrument_code(
        instrument_code
    )
    summary = dict(instrument=instrument_code, contracts=len(contracts), daily=0, hourly=0, errors=0)

    for contract in contracts:
        try:
            merged = price_data.get_merged_prices_for_contract_object(contract)
            if len(merged) == 0:
                continue
            daily, hourly = split_merged_prices(merged)
            if len(daily) > 0:
                summary["daily"] += 1
                if commit:
                    price_data.write_prices_at_frequency_for_contract_object(
                        contract,
                        futures_price_data=futuresContractPrices(daily),
                        ignore_duplication=False,
                        frequency=DAILY_PRICE_FREQ,
                    )
            if len(hourly) > 0:
                summary["hourly"] += 1
                if commit:
                    price_data.write_prices_at_frequency_for_contract_object(
                        contract,
                        futures_price_data=futuresContractPrices(hourly),
                        ignore_duplication=False,
                        frequency=HOURLY_FREQ,
                    )
        except Exception:
            summary["errors"] += 1

    if not quiet:
        print(
            "  %-16s 合约 %4d  日线 %4d  小时线 %4d  失败 %d"
            % (
                summary["instrument"],
                summary["contracts"],
                summary["daily"],
                summary["hourly"],
                summary["errors"],
            ),
            flush=True,
        )

    return summary


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="从合并文件补出 Day@/Hour@ 分频文件")
    parser.add_argument("--commit", action="store_true", help="真正写库（默认 dry-run）")
    parser.add_argument("--instruments", nargs="*", default=None)
    parser.add_argument("--limit", type=int, default=None, help="只处理前 N 个品种")
    args = parser.parse_args(argv)

    diag = diagPrices()
    price_data = diag.db_futures_contract_price_data
    instruments = price_data.get_list_of_instrument_codes_with_merged_price_data()
    instruments = sorted(instruments)
    if args.instruments:
        wanted = {code.upper() for code in args.instruments}
        instruments = [code for code in instruments if code.upper() in wanted]
    if args.limit:
        instruments = instruments[: args.limit]

    print(
        "%s：%d 个品种"
        % ("[commit] 写分频文件" if args.commit else "[dry-run] 只统计", len(instruments)),
        flush=True,
    )

    totals = dict(daily=0, hourly=0, errors=0, contracts=0)
    for instrument_code in instruments:
        summary = seed_instrument(instrument_code, commit=args.commit)
        totals["daily"] += summary["daily"]
        totals["hourly"] += summary["hourly"]
        totals["errors"] += summary["errors"]
        totals["contracts"] += summary["contracts"]

    print(
        "完成：合约 %d 个 → 日线 %d 个、小时线 %d 个，失败 %d"
        % (totals["contracts"], totals["daily"], totals["hourly"], totals["errors"])
    )
    if not args.commit:
        print("（dry-run，没有写任何文件；确认后加 --commit）")

    return 0


if __name__ == "__main__":
    sys.exit(main())
