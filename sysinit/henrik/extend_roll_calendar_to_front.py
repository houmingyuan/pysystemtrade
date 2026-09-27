"""
按 docs/roll_calendar_rules_cn.md §6 把换月日历尾巴延伸到「数据末端」。

背景：仓库的 roll calendar 是静态 CSV，日更只读不写。Norgate 导入/预生成日历的尾巴往往
停在旧月份，导致 multiple prices 的前端合约一直是一个已经到期的合约（例如 DAX 停在
20260900），IB 也就永远拿不到它的新行情 → data 停在导入日（2026-09-18）。

规则（只追加、不改历史）：
    1. held = 日历最后一行的 next_contract（即当前前端）；
    2. 下一个名义换月日 nominal = held 到期日 + RollOffsetDays；若 nominal > 数据末端 → 停止；
    3. 实际换月日 = 「> 上一行日期，且 held / next 两腿都有价」的最早交易日（三腿都有价优先）；
    4. 追加一行 (实际换月日, current=held, next=下一 held 合约, carry=按 CarryOffset)，held = next，回到 1。

默认 dry-run。用法：
    python sysinit/henrik/extend_roll_calendar_to_front.py --instruments DAX CAC
    python sysinit/henrik/extend_roll_calendar_to_front.py --instruments DAX CAC --commit
    python sysinit/henrik/extend_roll_calendar_to_front.py --all-stale --commit
"""

import argparse
import sys

import pandas as pd

from sysdata.data_blob import dataBlob
from sysobjects.contracts import contractDate
from sysobjects.rolls import contractDateWithRollParameters
from sysdata.csv.csv_roll_calendars import csvRollCalendarData
from sysdata.csv.csv_roll_parameters import csvRollParametersData
from sysproduction.data.broker import dataBroker
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


def ib_tradable_months(instrument_code: str) -> set:
    """IB 当前可交易的合约月份（'YYYYMM'）；取不到时返回空集合（表示不做该判据）。"""
    try:
        with dataBlob(log_name="Extend-Roll-Calendar") as data:
            dates = dataBroker(data).broker_futures_contract_data.get_list_of_contract_dates_for_instrument_code(
                instrument_code, allow_expired=False
            )
    except Exception:
        return set()

    months = set()
    for entry in dates:
        text = str(entry)[:6]
        if text.isdigit():
            months.add(text)
    return months


def next_held_contract(contract_date_str: str, roll_parameters):
    contract = contractDateWithRollParameters(
        contractDate(str(contract_date_str)), roll_parameters
    )
    return contract.next_held_contract()


def nominal_roll_date(contract_date_str: str, roll_parameters):
    contract = contractDateWithRollParameters(
        contractDate(str(contract_date_str)), roll_parameters
    )
    contract.contract_date.update_expiry_date_with_new_offset(
        roll_parameters.approx_expiry_offset
    )
    return contract.desired_roll_date


def extend_calendar(
    instrument_code: str, dry_run: bool = True, use_ib_availability: bool = False
) -> dict:
    calendar_data = csvRollCalendarData(ROLL_CALENDAR_PATH)
    roll_parameters = csvRollParametersData().get_roll_parameters(instrument_code)
    calendar = calendar_data.get_roll_calendar(instrument_code)
    price_dates = price_dates_by_contract(instrument_code)

    if len(calendar) == 0:
        return dict(instrument=instrument_code, added=0, status="没有日历")
    if not price_dates:
        return dict(instrument=instrument_code, added=0, status="没有合约价格")

    data_end = max(max(dates) for dates in price_dates.values() if dates)
    extended = calendar.copy()
    held = str(extended.iloc[-1].next_contract)
    previous_date = pd.DatetimeIndex(extended.index)[-1]
    added_rows = []
    tradable_months = ib_tradable_months(instrument_code) if use_ib_availability else set()

    for _ in range(60):  # 保护：最多延伸 60 次换月
        nominal = nominal_roll_date(held, roll_parameters)
        front_dates = price_dates.get(held, set())
        front_last = max(front_dates) if front_dates else None
        front_is_stale = (
            front_last is None or front_last < data_end - pd.Timedelta(days=3)
        )
        if tradable_months and held[:6] not in tradable_months:
            # IB 已经不再提供这个月份（例如已到期/已下市）→ 必须往前滚
            front_is_stale = True
        # 名义换月日还没到、且前端本身有最新行情 → 无需延伸；
        # 若前端已经没行情了（例如持有一个已到期合约），则即使名义日期过不了检查也要往前滚。
        if pd.Timestamp(nominal).normalize() > data_end and not front_is_stale:
            break

        next_contract = next_held_contract(held, roll_parameters)
        next_contract_str = str(next_contract.date_str)
        current_dates = price_dates.get(held, set())
        next_dates = price_dates.get(next_contract_str, set())
        valid_dates = sorted(
            date for date in current_dates & next_dates if date > previous_date
        )
        if not valid_dates:
            return dict(
                instrument=instrument_code,
                added=len(added_rows),
                status="%s→%s 找不到可用换月日" % (held, next_contract_str),
            )

        carry_contract_str = str(next_contract.carry_contract().date_str)
        carry_dates = price_dates.get(carry_contract_str, set())
        three_leg = [date for date in valid_dates if date in carry_dates]
        roll_date = three_leg[0] if three_leg else valid_dates[0]

        added_rows.append(
            dict(
                DATE_TIME=roll_date,
                current_contract=held,
                next_contract=next_contract_str,
                carry_contract=carry_contract_str,
            )
        )
        held = next_contract_str
        previous_date = roll_date

    if not added_rows:
        return dict(instrument=instrument_code, added=0, status="已是最新（无需延伸）")

    new_rows = pd.DataFrame(added_rows).set_index("DATE_TIME")
    extended = pd.concat([extended, new_rows])

    if not extended.index.is_unique or not extended.index.is_monotonic_increasing:
        return dict(instrument=instrument_code, added=0, status="延伸后日期重复/非单调，未写入")
    chain_ok = all(
        str(extended.iloc[k].next_contract) == str(extended.iloc[k + 1].current_contract)
        for k in range(len(extended) - 1)
    )
    if not chain_ok:
        return dict(instrument=instrument_code, added=0, status="延伸后链式不连续，未写入")

    if dry_run:
        return dict(
            instrument=instrument_code,
            added=len(added_rows),
            status="[dry-run] 将追加 %d 行，末行 %s→%s"
            % (len(added_rows), added_rows[-1]["current_contract"], added_rows[-1]["next_contract"]),
        )

    calendar_data.add_roll_calendar(instrument_code, extended, ignore_duplication=True)
    return dict(
        instrument=instrument_code,
        added=len(added_rows),
        status="已追加 %d 行，前端→%s" % (len(added_rows), added_rows[-1]["next_contract"]),
    )


def stale_instruments() -> list:
    """前端合约没有最新行情（multiple prices 末端明显落后）的品种。"""
    price_data = diagPrices().db_futures_contract_price_data
    instruments = price_data.get_list_of_instrument_codes_with_merged_price_data()
    stale = []
    for instrument_code in instruments:
        try:
            final_prices = price_data.get_merged_prices_for_instrument(
                instrument_code
            ).final_prices()
            if not final_prices:
                continue
            calendar = csvRollCalendarData(ROLL_CALENDAR_PATH).get_roll_calendar(
                instrument_code
            )
            if len(calendar) == 0:
                continue
            front = str(calendar.iloc[-1].next_contract)
            front_dates = pd.DatetimeIndex(pd.Series(final_prices[front]).index)
            data_end = max(
                pd.DatetimeIndex(pd.Series(series).index).max()
                for series in final_prices.values()
            )
            if front_dates.max() < data_end - pd.Timedelta(days=3):
                stale.append(instrument_code)
        except Exception:
            continue
    return sorted(stale)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="按 §6 延伸换月日历尾巴")
    parser.add_argument("--instruments", nargs="*", default=None)
    parser.add_argument("--all-stale", action="store_true", help="自动挑出前端缺数据的品种")
    parser.add_argument(
        "--use-ib-availability",
        action="store_true",
        help="用 IB 当前可交易月份判断前端是否已下市（需连 IB）",
    )
    parser.add_argument("--commit", action="store_true")
    args = parser.parse_args(argv)

    instruments = args.instruments or []
    if args.all_stale or not instruments:
        instruments = stale_instruments()
        print("检测到前端缺近期数据的品种 %d 个: %s" % (len(instruments), instruments), flush=True)

    for instrument_code in instruments:
        result = extend_calendar(
            instrument_code,
            dry_run=not args.commit,
            use_ib_availability=args.use_ib_availability,
        )
        print("%-14s %s" % (result["instrument"], result["status"]), flush=True)

    return 0


if __name__ == "__main__":
    sys.exit(main())
