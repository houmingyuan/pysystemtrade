#!/usr/bin/env python
"""
导入 Barchart 导出批次（FIR-215 / FIR-217）。

与 batch_backfill_barchart.py 的区别：本脚本面向「已有数据的品种补段」，默认走 MERGE
（而不是首次创建），因此适用于批次 1（21 个缺口品种）；批次 2/3 的全新品种请加 --create。

流程：表头规范化（Latest -> Close）-> 逐品种导入合约价格 -> 成交量法重建换月日历
      -> multiple prices -> adjusted prices。

用法：
    python3 sysinit/henrik/import_barchart_batch.py --datapath /path/to/export --dry-run
    python3 sysinit/henrik/import_barchart_batch.py --datapath /path/to/export
    python3 sysinit/henrik/import_barchart_batch.py --datapath /path/to/export --create
"""

import argparse
import glob
import os
import subprocess

import pandas as pd

from sysdata.csv.csv_futures_contract_prices import ConfigCsvFuturesPrices
from syscore.constants import arg_not_supplied
from sysinit.futures.adjustedprices_from_db_multiple_to_db import (
    process_adjusted_prices_single_instrument,
)
from sysinit.futures.contract_prices_from_split_freq_csv_to_db import (
    init_db_with_split_freq_csv_prices_for_code,
)
from sysinit.futures.multipleprices_from_db_prices_and_csv_calendars_to_db import (
    process_multiple_prices_single_instrument,
)
from sysinit.futures.rollcalendars_from_db_prices_to_csv import (
    build_and_write_roll_calendar,
)

ADJUSTED_PATH = "/Users/henrik/data/parquet/futures_adjusted_prices"

BARCHART_CONFIG = ConfigCsvFuturesPrices(
    input_date_index_name="Time",
    input_skiprows=0,
    input_skipfooter=0,
    input_date_format="%Y-%m-%dT%H:%M:%S%z",
    input_column_mapping=dict(
        OPEN="Open", HIGH="High", LOW="Low", FINAL="Close", VOLUME="Volume"
    ),
)


def normalise_headers(datapath: str) -> int:
    fixed = 0
    for path in glob.glob(os.path.join(datapath, "*.csv")):
        with open(path) as price_file:
            header = price_file.readline()
        if ",Latest," not in header:
            continue
        with open(path) as price_file:
            content = price_file.read()
        content = content.replace(
            "Time,Open,High,Low,Latest,Volume", "Time,Open,High,Low,Close,Volume", 1
        )
        with open(path, "w") as price_file:
            price_file.write(content)
        fixed += 1

    return fixed


def instruments_in_directory(datapath: str) -> list:
    codes = set()
    for path in glob.glob(os.path.join(datapath, "*.csv")):
        parts = os.path.basename(path).split("_")
        if len(parts) < 3:
            continue
        codes.add("_".join(parts[1:-1]))

    return sorted(codes)


def last_adjusted_date(instrument_code: str):
    path = f"{ADJUSTED_PATH}/{instrument_code}.parquet"
    if not os.path.exists(path):
        return None
    return pd.read_parquet(path).index[-1].date()


def import_instrument(instrument_code: str, datapath: str, create: bool) -> str:
    before = last_adjusted_date(instrument_code)
    init_db_with_split_freq_csv_prices_for_code(
        instrument_code, datapath=datapath, csv_config=BARCHART_CONFIG
    )
    # 优先成交量法重建日历；成交量缺失（季度挂牌、Barchart 无 volume）时回退到
    # rollconfig 参数法，否则新品种的链条永远建不起来（GILT2/GILT5 就是这种情形）。
    try:
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
    except subprocess.CalledProcessError:
        build_and_write_roll_calendar(
            instrument_code,
            output_datapath=arg_not_supplied,
            write=True,
            check_before_writing=False,
        )
    process_multiple_prices_single_instrument(
        instrument_code,
        adjust_calendar_to_prices=False,
        MERGE_FLAG=not create,
        ADD_TO_DB=True,
    )
    process_adjusted_prices_single_instrument(
        instrument_code, ADD_TO_DB=True, MERGE_ADJUSTED_PRICES=not create
    )
    after = last_adjusted_date(instrument_code)

    return f"{instrument_code}: {before} -> {after}"


def main():
    parser = argparse.ArgumentParser(description="导入 Barchart 导出批次")
    parser.add_argument("--datapath", required=True)
    parser.add_argument("--create", action="store_true", help="全新品种（首次构建）")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--report", default="/private/tmp/barchart_import_report.csv")
    args = parser.parse_args()

    fixed = normalise_headers(args.datapath)
    codes = instruments_in_directory(args.datapath)
    existing = [code for code in codes if last_adjusted_date(code) is not None]
    print(
        f"目录内品种 {len(codes)} 个（已有数据 {len(existing)}、全新 {len(codes) - len(existing)}）；"
        f"表头规范化 {fixed} 个文件",
        flush=True,
    )
    if args.dry_run:
        for code in codes:
            print(f"  {code}: 当前截止 {last_adjusted_date(code)}", flush=True)
        return

    rows = []
    for index, instrument_code in enumerate(codes, start=1):
        print(f"[{index}/{len(codes)}] {instrument_code}", flush=True)
        row = dict(instrument=instrument_code, status="OK")
        try:
            row["result"] = import_instrument(
                instrument_code, args.datapath, create=args.create
            )
        except Exception as error:
            row["status"] = f"FAILED: {type(error).__name__}: {error}"[:160]
        rows.append(row)
        pd.DataFrame(rows).to_csv(args.report, index=False)

    print(f"完成，报告：{args.report}", flush=True)


if __name__ == "__main__":
    main()
