"""
修复前端（priced）合约与换月日历末端（FIR-131）。
用途：
    python sysinit/henrik/repair_front_contracts.py --dry-run
    python sysinit/henrik/repair_front_contracts.py
    python sysinit/henrik/repair_front_contracts.py --instruments CORN SP500
    python sysinit/henrik/repair_front_contracts.py --recent-only HANG --recent-from 2025-10-01
做两件事：
1. 用按日期对齐（normalize 到当日 23:00 并去重）的合约价格构建 multiple prices，
   消除 Day 合约（23:00）与 Hour 合约（21:30/01:00/02:00）时间戳不一致导致的静默截断；
2. 用近期成交量判断真正的前端合约，砍掉日历末端指向非前端合约的“提前换月”行。
"""
import argparse
import sys

import pandas as pd

from syscore.constants import arg_not_supplied
from sysdata.csv.csv_roll_calendars import csvRollCalendarData
from sysdata.csv.csv_roll_parameters import csvRollParametersData
from sysinit.futures.adjustedprices_from_db_multiple_to_db import (
    process_adjusted_prices_single_instrument,
)
from sysinit.futures.build_roll_calendars import adjust_to_price_series
from sysinit.futures.multipleprices_from_db_prices_and_csv_calendars_to_db import (
    add_phantom_row,
)
from sysobjects.dict_of_futures_per_contract_prices import (
    dictFuturesContractFinalPrices,
)
from sysobjects.multiple_prices import futuresMultiplePrices
from sysproduction.data.prices import diagPrices

ROLL_CALENDAR_PATH = "data/futures/roll_calendars_csv"
DAILY_STAMP_HOUR = 23
VOLUME_LOOKBACK_DAYS = 5

diag_prices = diagPrices()


def daily_aligned_final_prices(instrument_code: str) -> dictFuturesContractFinalPrices:
    """取全部合约收盘价并把时间戳统一到当日 23:00（同日多条保留最后一条）。"""
    raw = diag_prices.db_futures_contract_price_data.get_merged_prices_for_instrument(
        instrument_code
    )
    aligned = {}
    for contract_key, series in raw.final_prices().items():
        series = pd.Series(series).copy()
        index = pd.DatetimeIndex(series.index)
        series.index = index.normalize() + pd.Timedelta(hours=DAILY_STAMP_HOUR)
        series = series[~series.index.duplicated(keep="last")].sort_index()
        aligned[contract_key] = series

    return dictFuturesContractFinalPrices(aligned)


def current_front_contract_by_volume(instrument_code: str):
    """最近若干交易日成交量最大的合约即真正的前端合约。"""
    contracts = diag_prices.db_futures_contract_price_data.get_merged_prices_for_instrument(
        instrument_code
    )
    frames = {}
    latest_date = None
    for contract_key in contracts.keys():
        frame = pd.DataFrame(contracts[contract_key])
        if frame.empty or "VOLUME" not in frame.columns:
            continue
        frame = frame[~frame.index.duplicated(keep="last")].sort_index()
        frames[contract_key] = frame
        if latest_date is None or frame.index[-1] > latest_date:
            latest_date = frame.index[-1]

    if latest_date is None:
        return None

    # 只看最近几个交易日的行情，避免把很久以前的合约算成前端
    recent_cutoff = latest_date - pd.Timedelta(days=VOLUME_LOOKBACK_DAYS * 3)
    best_volume = -1.0
    best_contract = None
    for contract_key, frame in frames.items():
        recent = frame[frame.index >= recent_cutoff]
        if len(recent) == 0:
            continue
        volume = float(pd.to_numeric(recent["VOLUME"], errors="coerce").sum())
        if volume > best_volume:
            best_volume = volume
            best_contract = int(contract_key)

    return best_contract


def trim_spurious_trailing_rows(roll_calendar: pd.DataFrame, front_contract: int):
    """从末尾往前砍掉 next_contract 不是前端合约的行。"""
    trimmed = roll_calendar
    while len(trimmed) > 1 and int(trimmed.iloc[-1].next_contract) != front_contract:
        trimmed = trimmed.iloc[:-1]

    if int(trimmed.iloc[-1].next_contract) != front_contract:
        raise Exception("日历中没有以 %s 为前端合约的行，需要重新生成日历" % front_contract)

    return trimmed


def build_multiple_prices(
    instrument_code: str, roll_calendar, dict_of_closing_prices, adjust_calendar: bool = True
) -> futuresMultiplePrices:
    roll_parameters = csvRollParametersData().get_roll_parameters(instrument_code)
    roll_calendar = add_phantom_row(roll_calendar, dict_of_closing_prices, roll_parameters)
    if adjust_calendar:
        # 注意：adjust 需要换月两端合约有同一时间戳，遇到“到期即换月、两合约不重叠”
        # 的品种会把整段日历截断，这类品种用 --no-adjust 直接按日历构建
        roll_calendar = adjust_to_price_series(roll_calendar, dict_of_closing_prices)
    roll_calendar = add_phantom_row(roll_calendar, dict_of_closing_prices, roll_parameters)

    return futuresMultiplePrices.create_from_raw_data(
        roll_calendar, dict_of_closing_prices
    )


def repair_instrument(
    instrument_code,
    dry_run=False,
    recent_only_cutoff=None,
    allow_missing_front=False,
    trim_calendar=True,
    adjust_calendar=True,
):
    roll_calendar_data = csvRollCalendarData(ROLL_CALENDAR_PATH)
    roll_calendar = roll_calendar_data.get_roll_calendar(instrument_code)
    front_contract = current_front_contract_by_volume(instrument_code)

    if recent_only_cutoff is not None:
        roll_calendar = roll_calendar[roll_calendar.index >= recent_only_cutoff]

    try:
        trimmed = (
            trim_spurious_trailing_rows(roll_calendar, front_contract)
            if trim_calendar
            else roll_calendar
        )
    except Exception:
        if not allow_missing_front:
            raise
        # 该品种的换月周期配置本来就到不了成交前端（例如按年换月的品种），
        # 此时保留现有日历，只做按日期对齐的重建
        print(
            "  %-14s 成交量前端 %s 不在日历周期内，保留现有日历"
            % (instrument_code, front_contract)
        )
        trimmed = roll_calendar
    rows_dropped = len(roll_calendar) - len(trimmed)

    dict_of_closing_prices = daily_aligned_final_prices(instrument_code)
    multiple_prices = build_multiple_prices(
        instrument_code, trimmed, dict_of_closing_prices, adjust_calendar=adjust_calendar
    )

    if recent_only_cutoff is not None:
        stored = pd.DataFrame(
            diag_prices.db_futures_multiple_prices_data.get_multiple_prices(instrument_code)
        )
        multiple_prices = futuresMultiplePrices(
            pd.concat(
                [
                    stored[stored.index < multiple_prices.index[0]],
                    pd.DataFrame(multiple_prices),
                ]
            )
        )

    last_multiple_date = multiple_prices.index[-1]
    print(
        "  %-14s front=%s rows_dropped=%d result_last=%s"
        % (instrument_code, front_contract, rows_dropped, last_multiple_date)
    )

    if dry_run:
        return multiple_prices

    # 用 --recent-only 时，日历被切成了近期片段，不能整份写回去（会把历史砍掉）
    if rows_dropped and recent_only_cutoff is None:
        roll_calendar_data.add_roll_calendar(instrument_code, trimmed, ignore_duplication=True)

    db_multiple_prices = diag_prices.db_futures_multiple_prices_data
    stored = pd.DataFrame(db_multiple_prices.get_multiple_prices(instrument_code))
    if (recent_only_cutoff is None) and last_multiple_date < stored.index[-1] - pd.Timedelta(days=7):
        raise Exception(
            "重建结果（%s）比库内（%s）短，拒绝覆盖" % (last_multiple_date, stored.index[-1])
        )

    db_multiple_prices.add_multiple_prices(instrument_code, multiple_prices, ignore_duplication=True)
    process_adjusted_prices_single_instrument(
        instrument_code,
        csv_adj_data_path=arg_not_supplied,
        ADD_TO_DB=True,
        ADD_TO_CSV=False,
        MERGE_ADJUSTED_PRICES=False,
    )

    return multiple_prices


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="修复前端合约与换月日历末端")
    parser.add_argument("--dry-run", action="store_true", help="只计算不写库")
    parser.add_argument("--instruments", nargs="*", default=None, help="只处理这些品种")
    parser.add_argument(
        "--recent-only",
        nargs="*",
        default=None,
        help="这些品种保留历史，只重建给定日期之后的行情（用于有历史空档的品种）",
    )
    parser.add_argument("--recent-from", default="2025-10-01", help="重建起点")
    parser.add_argument(
        "--allow-missing-front",
        action="store_true",
        help="换月周期到不了成交前端时保留现有日历，只做按日期对齐的重建",
    )
    parser.add_argument(
        "--no-trim",
        action="store_true",
        help="不订正日历末端，只用按日期对齐的价格重建",
    )
    parser.add_argument(
        "--no-adjust",
        action="store_true",
        help="不做换月日历对齐（用于换月两端合约不重叠、adjust 会误截断的品种）",
    )
    args = parser.parse_args(argv)

    if args.instruments:
        instrument_list = list(args.instruments)
    else:
        instrument_list = diag_prices.db_futures_multiple_prices_data.get_list_of_instruments()
    recent_only = set(args.recent_only or [])
    cutoff = pd.Timestamp(args.recent_from)

    succeeded, failed = [], []
    for instrument_code in instrument_list:
        try:
            repair_instrument(
                instrument_code,
                dry_run=args.dry_run,
                recent_only_cutoff=cutoff if instrument_code in recent_only else None,
                allow_missing_front=args.allow_missing_front,
                trim_calendar=not args.no_trim,
                adjust_calendar=not args.no_adjust,
            )
            succeeded.append(instrument_code)
        except Exception as error:
            failed.append((instrument_code, "%s: %s" % (type(error).__name__, error)))
            print("  %-14s FAILED %s" % (instrument_code, str(error)[:90]))

    print("\n成功 %d / %d" % (len(succeeded), len(instrument_list)))
    if failed:
        print("失败 %d 个：" % len(failed))
        for code, reason in failed:
            print("  - %s : %s" % (code, reason))

    return 0 if not failed else 1


if __name__ == "__main__":
    sys.exit(main())
