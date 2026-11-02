"""
按成交量重建换月日历（FIR-134）。

规则：逐日取成交量最大的合约作为“持有合约”，当持有合约向前切换时记为一次换月，
行写成 (换月日, current=换月前持有, next=换月后持有, carry=按 rollconfig 推导)，
与 PST 的 roll calendar 语义一致（row 的 next_contract 是换月后持有的合约）。

carry 合约**按 rollconfig 的 CarryOffset 推导**（-1 = 上月、+1 = 下月），不再固定为
「换月前持有」——那样会把 VIX 这类 CarryOffset=+1 的口径改回去。

对单日成交量毛刺用 rolling(3).median() 平滑；只接受向前（月份变大）的切换。

默认只在现有日历末尾追加换月，不改写历史行：重建只从 --min-date 起算，整体替换会把
更早的历史截掉（2026-10-21 的失滚重建就把 CAC、NIKKEI-SGX 截到了 2000 年）。
新品种首次构建、或确实要替换现有日历时加 --full。

用法：
    python sysinit/henrik/rebuild_roll_calendar_from_volume.py --instrument VIX --dry-run
    python sysinit/henrik/rebuild_roll_calendar_from_volume.py --instrument VIX
    python sysinit/henrik/rebuild_roll_calendar_from_volume.py --instrument VIX --full
"""
import argparse
import glob
import os
import sys

import pandas as pd

from sysdata.csv.csv_roll_calendars import csvRollCalendarData, roll_calendar_directory
from sysdata.csv.csv_roll_parameters import csvRollParametersData
import sysinit.futures.rebuild_roll_calendar_from_prices as R
from sysobjects.contract_dates_and_expiries import contractDate
from sysobjects.rolls import contractDateWithRollParameters

CP_PATH = "/Users/henrik/data/parquet/futures_contract_prices"
ROLL_CALENDAR_PATH = roll_calendar_directory()
SMOOTH_DAYS = 3
NEAR_MAX_RATIO = 0.5


def daily_volume_by_contract(instrument_code: str, min_date: str) -> pd.DataFrame:
    series = {}
    for path in glob.glob(f"{CP_PATH}/{instrument_code}#*.parquet"):
        contract = int(os.path.basename(path).split("#")[1][:-8])
        prices = pd.read_parquet(path)
        prices = prices[prices.index >= pd.Timestamp(min_date)]
        if prices.empty:
            continue
        series[contract] = (
            pd.to_numeric(prices["VOLUME"], errors="coerce")
            .groupby(pd.DatetimeIndex(prices.index).normalize())
            .sum()
        )

    return pd.DataFrame(series).fillna(0.0)


def calendar_rows_from_volume(instrument_code: str, min_date: str) -> pd.DataFrame:
    roll_parameters = csvRollParametersData().get_roll_parameters(instrument_code)
    volumes = daily_volume_by_contract(instrument_code, min_date)
    volumes = volumes.rolling(SMOOTH_DAYS, min_periods=1).median()
    # 成交量最大的合约里，若存在成交额接近（>= 50%）的更近月合约，取更近的那个，
    # 避免单日远月合约的成交量毛刺把持有合约往前推。
    leader = volumes.apply(
        lambda row: min(
            [
                contract
                for contract, volume in row.items()
                if volume > 0 and volume >= NEAR_MAX_RATIO * row.max()
            ],
            default=row.idxmax(),
        ),
        axis=1,
    )
    leader = leader[volumes.sum(axis=1) > 0]

    rows = []
    held = None
    for date, candidate in leader.items():
        if held is None:
            held = candidate
            continue
        if candidate <= held:
            continue
        rows.append(
            (
                date,
                held,
                candidate,
                carry_contract_for_held(
                    held, roll_parameters, available=set(volumes.columns)
                ),
            )
        )
        held = candidate

    calendar = pd.DataFrame(
        [row[1:] for row in rows],
        columns=["current_contract", "next_contract", "carry_contract"],
        index=[row[0] for row in rows],
    )
    calendar.index.name = R.INDEX_NAME

    return calendar


def carry_contract_for_held(held_contract: int, roll_parameters, available=None) -> int:
    """
    carry 合约由 rollconfig 的 CarryOffset 决定（复用 contractDateWithRollParameters）。

    推不出来时（rollconfig 到不了、合约不在 rollcycle 里）退回「换月前持有」并告警，
    不让整个重建失败。

    另外：季度挂牌品种（如 COPPER-micro、NIKKEI）按 CarryOffset 推出的月份可能根本
    没有挂牌，此时取价格库里最接近的合约月份，避免 multiple prices 报
    「Missing contract ... in middle of roll calendar」。
    """
    try:
        held = contractDateWithRollParameters(
            contractDate(str(held_contract)), roll_parameters
        )
        carry_contract = int(held.carry_contract().date_str)
    except Exception as error:
        print(
            "  WARN: 合约 %s 无法按 rollconfig 推导 carry（%s: %s），退回换月前持有"
            % (held_contract, type(error).__name__, error)
        )
        carry_contract = int(held_contract)

    if available and carry_contract not in available:
        # 优先吸附到「当前持有」合约：季度挂牌品种按 CarryOffset 推出来的月份通常
        # 根本没有挂牌（如 COPPER-micro、NIKKEI、OMX），若吸附到 next 会出现
        # current/next/carry 同一月份的错误语义。
        if held_contract in available:
            carry_contract = int(held_contract)
        else:
            carry_contract = min(
                available,
                key=lambda contract: (abs(contract - carry_contract), contract),
            )

    return carry_contract


def extend_existing_calendar(existing: pd.DataFrame, rebuilt: pd.DataFrame) -> pd.DataFrame:
    """
    把重建结果里「换入合约晚于现有最后持有合约」的换月接到现有日历末尾，历史行不动。

    接缝必须连续：第一条追加行的 current 等于现有最后一行的 next，且日期更晚；
    接不上就抛 ValueError，宁可不写也不写出断链的日历。
    """
    if existing.empty:
        return rebuilt

    last_held = int(existing.iloc[-1].next_contract)
    tail = rebuilt[rebuilt.next_contract.astype(int) > last_held]
    if tail.empty:
        return existing

    first_current = int(tail.iloc[0].current_contract)
    if first_current != last_held or tail.index[0] <= existing.index[-1]:
        raise ValueError(
            "重建结果与现有日历接不上：现有最后持有 %s（%s 换入），重建的第一条追加行为 %s -> %s（%s）"
            % (
                last_held,
                existing.index[-1].date(),
                first_current,
                int(tail.iloc[0].next_contract),
                tail.index[0].date(),
            )
        )

    return pd.concat([existing, tail])


def check_chain(calendar: pd.DataFrame) -> list:
    breaks = []
    for i in range(len(calendar) - 1):
        if int(calendar.iloc[i].next_contract) != int(calendar.iloc[i + 1].current_contract):
            breaks.append(
                (
                    str(calendar.index[i].date()),
                    int(calendar.iloc[i].next_contract),
                    str(calendar.index[i + 1].date()),
                    int(calendar.iloc[i + 1].current_contract),
                )
            )

    return breaks


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="按成交量重建换月日历")
    parser.add_argument("--instrument", required=True)
    parser.add_argument("--min-date", default="2000-01-01")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument(
        "--full",
        action="store_true",
        help="用重建结果整体替换现有日历（默认只在末尾追加，不改写历史行）",
    )
    args = parser.parse_args(argv)

    rebuilt = calendar_rows_from_volume(args.instrument, args.min_date)
    if rebuilt.empty:
        print("没有可用数据，未生成日历")
        return 1

    calendar_data = csvRollCalendarData(ROLL_CALENDAR_PATH)
    existing = calendar_data.get_roll_calendar(args.instrument)

    if args.full:
        calendar = rebuilt
    else:
        try:
            calendar = extend_existing_calendar(existing, rebuilt)
        except ValueError as error:
            print("未写入：%s" % error)
            return 1
        if len(calendar) == len(existing) and not existing.empty:
            print("%s：没有新的换月，未写入" % args.instrument)
            return 0

    print("%s：现有日历 %d 行 -> %s后 %d 行（按成交量重建 %d 行，%s 起）"
          % (args.instrument, len(existing), "整体替换" if args.full else "末尾追加",
             len(calendar), len(rebuilt), args.min_date))
    print(calendar.tail(6).to_string())
    breaks = check_chain(calendar)
    print("链条断点：%d" % len(breaks))
    for item in breaks[:5]:
        print("   ", item)

    if args.dry_run:
        print("dry-run，未写入")
        return 0

    calendar_data.add_roll_calendar(
        args.instrument, R.rollCalendar(calendar), ignore_duplication=True
    )
    print("已写入 %s/%s.csv" % (ROLL_CALENDAR_PATH, args.instrument))
    return 0


if __name__ == "__main__":
    sys.exit(main())
