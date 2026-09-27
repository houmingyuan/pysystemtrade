"""
把换月日历里「同一天多行」的第二行及其后各行，错开到下一个「两侧合约都有价」的交易日。

为什么需要：
    roll_calendar.loc[date] 命中两行时，multiple prices 构建会直接报
    「Missing contracts in middle of roll calendar ... not in price data」。
    VIX 曾经有 7 组（FIR-142 手工修掉），SOFR / SONIA3 的日历也有同样的重复日期，
    导致它们的 multiple prices 一直建不出来。

做法（与 FIR-142 相同）：
    对每一组同日多行，保留第一行的日期，把后续各行依次挪到「> 上一行日期 且
    current/next 两个合约都有价」的最早交易日；三腿都有价时优先。链式连续性不受影响
    （只改日期，不改合约）。

默认 dry-run。用法：
    python sysinit/henrik/fix_duplicate_roll_dates.py --instruments SOFR SONIA3
    python sysinit/henrik/fix_duplicate_roll_dates.py --instruments SOFR SONIA3 --commit
"""

import argparse
import sys

import pandas as pd

from sysdata.csv.csv_roll_calendars import csvRollCalendarData
from sysproduction.data.prices import diagPrices

ROLL_CALENDAR_PATH = "data/futures/roll_calendars_csv"


def price_dates_by_contract(instrument_code: str) -> dict:
    price_data = diagPrices().db_futures_contract_price_data
    final_prices = price_data.get_merged_prices_for_instrument(
        instrument_code
    ).final_prices()
    return {
        str(contract): set(pd.DatetimeIndex(pd.Series(series).index).normalize())
        for contract, series in final_prices.items()
    }


def fix_duplicate_dates(instrument_code: str, dry_run: bool = True) -> dict:
    calendar_data = csvRollCalendarData(ROLL_CALENDAR_PATH)
    calendar = calendar_data.get_roll_calendar(instrument_code)
    dates = pd.DatetimeIndex(calendar.index).normalize()

    result = dict(
        instrument=instrument_code,
        rows_before=len(calendar),
        duplicate_dates=int(pd.Series(dates).duplicated().sum()),
        moved=0,
        status="",
    )
    if result["duplicate_dates"] == 0:
        result["status"] = "没有重复日期"
        return result

    price_dates = price_dates_by_contract(instrument_code)
    fixed = calendar.copy()
    fixed.index = dates

    previous_date = None
    for position in range(len(fixed)):
        row = fixed.iloc[position]
        current_contract = str(row.current_contract)
        next_contract = str(row.next_contract)
        carry_contract = str(row.carry_contract)

        current_dates = price_dates.get(current_contract, set())
        next_dates = price_dates.get(next_contract, set())
        valid_dates = sorted(current_dates & next_dates)

        if previous_date is not None:
            valid_dates = [date for date in valid_dates if date > previous_date]
        if not valid_dates:
            result["status"] = "第 %d 行找不到可用日期（%s→%s）" % (
                position,
                current_contract,
                next_contract,
            )
            return result

        nominal = fixed.index[position]
        if previous_date is None or nominal > previous_date:
            # 日期本身没问题（不与上一行冲突）→ 保持原样，最小改动
            chosen = nominal
        else:
            # 与前一行同日（或更早）：挪到「> 上一行日期 且两腿都有价」的最早交易日，
            # 三腿都有价时优先
            three_leg_dates = [
                date
                for date in valid_dates
                if date in price_dates.get(carry_contract, set())
            ]
            if three_leg_dates:
                chosen = three_leg_dates[0]
            else:
                chosen = valid_dates[0]

        if chosen != nominal:
            fixed.index.values[position] = chosen
            result["moved"] += 1
        previous_date = chosen

    if not fixed.index.is_unique:
        result["status"] = "错开后仍有重复日期，未写入"
        return result

    chain_ok = all(
        str(fixed.iloc[k].next_contract) == str(fixed.iloc[k + 1].current_contract)
        for k in range(len(fixed) - 1)
    )
    if not chain_ok:
        result["status"] = "错开后链式不连续，未写入"
        return result

    if dry_run:
        result["status"] = "[dry-run] 将移动 %d 行的日期" % result["moved"]
        return result

    calendar_data.add_roll_calendar(instrument_code, fixed, ignore_duplication=True)
    result["status"] = "已写入（移动 %d 行）" % result["moved"]
    return result


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="修正换月日历里同一天多行的问题")
    parser.add_argument("--instruments", nargs="+", required=True)
    parser.add_argument("--commit", action="store_true", help="真正写回 CSV（默认 dry-run）")
    args = parser.parse_args(argv)

    for instrument_code in args.instruments:
        result = fix_duplicate_dates(instrument_code, dry_run=not args.commit)
        print(
            "%-12s 行数 %d  重复日期 %d  %s"
            % (
                result["instrument"],
                result["rows_before"],
                result["duplicate_dates"],
                result["status"],
            ),
            flush=True,
        )

    return 0


if __name__ == "__main__":
    sys.exit(main())
