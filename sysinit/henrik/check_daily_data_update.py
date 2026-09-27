"""
日更链路的数据面校验（FIR-162）。

每一步都 exit 0，不代表数据真的推进了：价格尖峰被拒、品种没有采样合约、
multiple prices 没跟上合约价格，都会静默表现成「今天的数据没更新」。
本脚本把这些信号集中检查一遍，发现异常就打印清单并**非零退出**，
这样 run_daily_data_update 的步骤级失败汇总能看见「数据没推进」。

检查项：
  1. 当日日志里的价格尖峰被拒（`moved too much`）——按**去重后的合约数**计，
     超过 --max-spikes（默认 0）即失败。历史经验：正常日 0 条，2026-09-24 事故日 132 个合约。
  2. 当日日志里「No contracts marked for sampling for XXX」的品种——默认只报告，
     只有所有品种都没有采样合约（采样表整体为空、update_historical_prices 会空转）
     才判失败；加 --fail-on-any-no-sampling 可改成任一品种即失败。
  3. 每个品种的 multiple prices 末端是否落后合约价格末端超过 --max-stale-days 天。

用法：
    python sysinit/henrik/check_daily_data_update.py             # 用今天（或最近一份）日志
    python sysinit/henrik/check_daily_data_update.py --log /Volumes/data/systrade/log/update_20260928.log
    python sysinit/henrik/check_daily_data_update.py --max-spikes 5 --max-stale-days 3
    python sysinit/henrik/check_daily_data_update.py --skip-tail-check
"""

import argparse
import glob
import os
import re
import sys
from datetime import date

import pandas as pd

DEFAULT_LOG_DIR = "/Volumes/data/systrade/log"
LOG_FILE_PATTERN = "update_*.log"

SPIKE_PATTERN = re.compile(
    r"instrument_code': '([^']+)', 'contract_date': '([^']+)'.*moved too much"
)
NO_SAMPLING_PATTERN = re.compile(
    r"No contracts marked for sampling for ([A-Za-z0-9_\-\.]+)"
)

DEFAULT_MAX_SPIKES = 0
DEFAULT_MAX_STALE_DAYS = 7
MAX_LISTED = 25


def default_log_path(log_dir: str = DEFAULT_LOG_DIR, today: date = None) -> str:
    """今天那份 update_YYYYMMDD.log；没有就退回最近的一份。"""
    if today is None:
        today = date.today()

    todays_log = os.path.join(log_dir, "update_%s.log" % today.strftime("%Y%m%d"))
    if os.path.exists(todays_log):
        return todays_log

    candidates = sorted(glob.glob(os.path.join(log_dir, LOG_FILE_PATTERN)))
    if not candidates:
        raise FileNotFoundError("在 %s 下找不到 %s" % (log_dir, LOG_FILE_PATTERN))

    return candidates[-1]


def spike_rejections_from_log(path: str):
    """返回（去重后的 (instrument, contract) 列表，命中的日志行数）。"""
    pairs = []
    seen = set()
    total_lines = 0
    for line in open(path, errors="ignore"):
        match = SPIKE_PATTERN.search(line)
        if match is None:
            continue
        total_lines += 1
        pair = (match.group(1), match.group(2))
        if pair not in seen:
            seen.add(pair)
            pairs.append(pair)

    return pairs, total_lines


def instruments_without_sampling_contracts(path: str):
    found = []
    seen = set()
    for line in open(path, errors="ignore"):
        match = NO_SAMPLING_PATTERN.search(line)
        if match is None:
            continue
        instrument_code = match.group(1)
        if instrument_code not in seen:
            seen.add(instrument_code)
            found.append(instrument_code)

    return found


def stale_multiple_prices(diag_prices, instrument_codes, max_stale_days: int):
    """
    返回 [(instrument, multiple_last, contract_last, 原因), ...]。

    multiple prices 末端落后合约价格末端超过 max_stale_days 天，说明构建没跟上
    （常见原因：换月日历陈旧、单品种构建抛错被容错版跳过）。
    """
    stale = []
    for instrument_code in instrument_codes:
        try:
            multiple_last = _last_multiple_prices_date(diag_prices, instrument_code)
            contract_last = _last_contract_price_date(diag_prices, instrument_code)
        except Exception as error:
            stale.append(
                (
                    instrument_code,
                    None,
                    None,
                    "%s: %s" % (type(error).__name__, error),
                )
            )
            continue

        if multiple_last is None or contract_last is None:
            continue

        if multiple_last < contract_last - pd.Timedelta(days=max_stale_days):
            stale.append((instrument_code, multiple_last, contract_last, "末端落后"))

    return stale


def _last_multiple_prices_date(diag_prices, instrument_code: str):
    multiple_prices = diag_prices.get_multiple_prices(instrument_code)
    index = pd.DatetimeIndex(pd.DataFrame(multiple_prices).index)
    if len(index) == 0:
        return None
    latest = index.max()
    return None if pd.isna(latest) else pd.Timestamp(latest)


def _last_contract_price_date(diag_prices, instrument_code: str):
    merged = (
        diag_prices.db_futures_contract_price_data.get_merged_prices_for_instrument(
            instrument_code
        )
    )
    latest = None
    for series in merged.final_prices().values():
        index = pd.DatetimeIndex(series.index)
        if len(index) == 0:
            continue
        candidate = index.max()
        if pd.isna(candidate):
            continue
        if latest is None or candidate > latest:
            latest = candidate

    return None if latest is None else pd.Timestamp(latest)


def instrument_codes_to_check(diag_prices, requested):
    if requested:
        return list(requested)

    return diag_prices.db_futures_contract_price_data.get_list_of_instrument_codes_with_merged_price_data()


def main(argv=None) -> int:
    _line_buffer_stdout()

    parser = argparse.ArgumentParser(description="日更链路的数据面校验")
    parser.add_argument("--log", default=None, help="要检查的更新日志，默认今天/最近一份")
    parser.add_argument(
        "--max-spikes",
        type=int,
        default=DEFAULT_MAX_SPIKES,
        help="允许的被拒合约数上限（默认 %d）" % DEFAULT_MAX_SPIKES,
    )
    parser.add_argument(
        "--max-stale-days",
        type=int,
        default=DEFAULT_MAX_STALE_DAYS,
        help="multiple prices 允许落后合约价格的天数（默认 %d）" % DEFAULT_MAX_STALE_DAYS,
    )
    parser.add_argument(
        "--skip-tail-check", action="store_true", help="跳过 multiple prices 末端检查"
    )
    parser.add_argument(
        "--fail-on-any-no-sampling",
        action="store_true",
        help="任一品种没有采样合约即失败（默认只在采样表整体为空时失败）",
    )
    parser.add_argument("--instruments", nargs="*", default=None, help="只检查这些品种")
    args = parser.parse_args(argv)

    try:
        log_path = args.log or default_log_path()
    except FileNotFoundError as error:
        print("ERROR: %s" % error)
        return 1

    if not os.path.exists(log_path):
        print("ERROR: 找不到更新日志 %s" % log_path)
        return 1

    print("=" * 70)
    print("数据面校验：日志 %s" % log_path)
    print("=" * 70)

    problems = []

    pairs, spike_lines = spike_rejections_from_log(log_path)
    print(
        "- 价格尖峰被拒：%d 行 / %d 个合约（阈值 %d）"
        % (spike_lines, len(pairs), args.max_spikes)
    )
    for instrument_code, contract_date in pairs[:MAX_LISTED]:
        print("    %s %s" % (instrument_code, contract_date))
    if len(pairs) > MAX_LISTED:
        print("    ...（其余 %d 个省略）" % (len(pairs) - MAX_LISTED))
    if len(pairs) > args.max_spikes:
        problems.append(
            "价格尖峰被拒 %d 个合约（> 阈值 %d），这些合约当日没有写入新数据"
            % (len(pairs), args.max_spikes)
        )

    no_sampling = instruments_without_sampling_contracts(log_path)
    print("- 没有采样合约的品种：%d 个 %s" % (len(no_sampling), ", ".join(no_sampling)))

    if args.skip_tail_check:
        print("- multiple prices 末端检查：已跳过")
        total_instruments = None
    else:
        total_instruments, tail_problems = _run_tail_check(args)
        problems.extend(tail_problems)

    problems.extend(
        _sampling_problems(
            no_sampling,
            total_instruments=total_instruments,
            fail_on_any=args.fail_on_any_no_sampling,
        )
    )

    print("=" * 70)
    if not problems:
        print("数据面校验通过")
        return 0

    print("数据面校验发现 %d 个问题：" % len(problems))
    for problem in problems:
        print("  - %s" % problem)
    print("=" * 70)

    return 1


def _line_buffer_stdout():
    """重定向到日志文件时也按行刷出，避免与库初始化日志交错。"""
    try:
        sys.stdout.reconfigure(line_buffering=True)
    except AttributeError:
        pass


def _sampling_problems(no_sampling, total_instruments=None, fail_on_any=False):
    """
    「没有采样合约」本身是常见现象（有些品种本来就不在采样表里），默认只报告；
    真正的事故是**采样表整体为空**——那时 update_historical_prices 会空转且退出码为 0。
    """
    if not no_sampling:
        return []

    if fail_on_any:
        return ["有 %d 个品种没有采样合约" % len(no_sampling)]

    if total_instruments is None:
        # 没查库，无法判断是否整体为空，只报告
        return []

    if len(no_sampling) >= total_instruments:
        return [
            "所有 %d 个品种都没有采样合约（采样表为空），update_historical_prices 会空转"
            % total_instruments
        ]

    return []


def _run_tail_check(args):
    from sysproduction.data.prices import diagPrices

    problems = []
    diag_prices = diagPrices()
    instrument_codes = instrument_codes_to_check(diag_prices, args.instruments)
    print(
        "- multiple prices 末端检查：%d 个品种（允许落后 %d 天）"
        % (len(instrument_codes), args.max_stale_days)
    )

    stale = stale_multiple_prices(
        diag_prices, instrument_codes, max_stale_days=args.max_stale_days
    )
    for instrument_code, multiple_last, contract_last, reason in stale[:MAX_LISTED]:
        print(
            "    %-16s multiple=%s contract=%s %s"
            % (instrument_code, multiple_last, contract_last, reason)
        )
    if len(stale) > MAX_LISTED:
        print("    ...（其余 %d 个省略）" % (len(stale) - MAX_LISTED))
    if stale:
        problems.append(
            "%d 个品种的 multiple prices 落后合约价格超过 %d 天"
            % (len(stale), args.max_stale_days)
        )

    return len(instrument_codes), problems


if __name__ == "__main__":
    sys.exit(main())
