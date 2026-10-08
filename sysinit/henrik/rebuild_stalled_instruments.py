#!/usr/bin/env python
"""
日更后自动重建「失滚品种」（FIR-219 / FIR-220）。

背景：部分品种的前端合约到期后，换月日历没有随成交量重新滚动，导致 multiple prices
停在旧日期（合约价格却在更新）。2026-10-08 手工验证：成交量法重建日历 +
multiple（不强对齐）+ adjusted 可修复其中大多数。

逻辑：
    a. 逐个品种比较 multiple prices 末端 vs 合约价格末端；
    b. 只处理「合约价格是新的（<= stale_days 天）但链条落后 > max_lag_days」的品种；
    c. 对这些品种：重建成交量法日历 -> multiple（adjust_calendar_to_prices=False, MERGE）
       -> adjusted（MERGE）；
    d. 输出修复前后日期；单品种失败不影响其余品种。

用法：
    python3 sysinit/henrik/rebuild_stalled_instruments.py --dry-run
    python3 sysinit/henrik/rebuild_stalled_instruments.py
"""

import argparse
import subprocess

import pandas as pd

from sysdata.data_blob import dataBlob
from sysinit.futures.adjustedprices_from_db_multiple_to_db import (
    process_adjusted_prices_single_instrument,
)
from sysinit.futures.multipleprices_from_db_prices_and_csv_calendars_to_db import (
    process_multiple_prices_single_instrument,
)
from sysinit.henrik.check_daily_data_update import (
    _last_contract_price_date,
    _last_multiple_prices_date,
)
from sysproduction.data.prices import diagPrices

ADJUSTED_PATH = "/Users/henrik/data/parquet/futures_adjusted_prices"


def stalled_instruments(
    diag, instrument_codes, max_lag_days: int = 3, stale_days: int = 5
) -> list:
    today = pd.Timestamp.today().normalize()
    stalled = []
    for instrument_code in instrument_codes:
        try:
            multiple_last = _last_multiple_prices_date(diag, instrument_code)
            contract_last = _last_contract_price_date(diag, instrument_code)
        except Exception:
            continue
        if multiple_last is None or contract_last is None:
            continue
        lag_days = (contract_last.normalize() - multiple_last.normalize()).days
        contract_age = (today - contract_last.normalize()).days
        if lag_days > max_lag_days and contract_age <= stale_days:
            stalled.append((instrument_code, multiple_last, contract_last))

    return stalled


def rebuild(instrument_code: str) -> str:
    before = pd.read_parquet(f"{ADJUSTED_PATH}/{instrument_code}.parquet").index[-1].date()
    subprocess.run(
        [
            "python3",
            "sysinit/henrik/rebuild_roll_calendar_from_volume.py",
            "--instrument",
            instrument_code,
        ],
        check=True,
        capture_output=True,
    )
    process_multiple_prices_single_instrument(
        instrument_code,
        adjust_calendar_to_prices=False,
        MERGE_FLAG=True,
        ADD_TO_DB=True,
    )
    process_adjusted_prices_single_instrument(
        instrument_code, ADD_TO_DB=True, MERGE_ADJUSTED_PRICES=True
    )
    after = pd.read_parquet(f"{ADJUSTED_PATH}/{instrument_code}.parquet").index[-1].date()

    return f"{instrument_code}: {before} -> {after}"


def main():
    parser = argparse.ArgumentParser(description="自动重建失滚品种")
    parser.add_argument("--max-lag-days", type=int, default=3)
    parser.add_argument("--stale-days", type=int, default=5)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    diag = diagPrices(dataBlob())
    instrument_codes = diag.get_list_of_instruments_in_multiple_prices()
    stalled = stalled_instruments(
        diag,
        instrument_codes,
        max_lag_days=args.max_lag_days,
        stale_days=args.stale_days,
    )
    print(f"待检查 {len(instrument_codes)} 个品种，失滚 {len(stalled)} 个", flush=True)
    for instrument_code, multiple_last, contract_last in stalled:
        if args.dry_run:
            print(
                f"{instrument_code}: multiple={multiple_last.date()} contract={contract_last.date()}",
                flush=True,
            )
            continue
        try:
            print(rebuild(instrument_code), flush=True)
        except Exception as error:
            print(
                f"{instrument_code}: 失败 {type(error).__name__}: {str(error)[:80]}",
                flush=True,
            )


if __name__ == "__main__":
    main()
