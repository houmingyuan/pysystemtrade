#!/usr/bin/env python
"""
批量补全：把 Barchart 备份里「Norgate 没有」的品种导入价格库。

流程（试点 FIR-212 已验证）：
    表头规范化（Latest → Close）→ 导入合约价格 → 成交量法重建换月日历
    → multiple prices（首次构建 MERGE_FLAG=False）→ adjusted prices

只追加新品种；已有合约价格的品种默认跳过（可用 --force 覆盖）。
逐个品种记录结果，单个失败不中断整批。

用法：
    python3 sysinit/henrik/batch_backfill_barchart.py \
        --datapath /private/tmp/barchart_all/barchart \
        --report docs/backfill_report.csv
"""

import argparse
import glob
import os
import subprocess

import pandas as pd

from sysdata.csv.csv_futures_contract_prices import ConfigCsvFuturesPrices
from sysinit.futures.adjustedprices_from_db_multiple_to_db import (
    process_adjusted_prices_single_instrument,
)
from sysinit.futures.contract_prices_from_split_freq_csv_to_db import (
    init_db_with_split_freq_csv_prices_for_code,
)
from sysinit.futures.multipleprices_from_db_prices_and_csv_calendars_to_db import (
    process_multiple_prices_single_instrument,
)

CP_PATH = "/Users/henrik/data/parquet/futures_contract_prices"
INSTRUMENT_CONFIG = "data/futures/csvconfig/instrumentconfig.csv"

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
    """把 Latest 列名统一成 Close；返回修改文件数。"""
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


def instruments_in_backup(datapath: str) -> list:
    codes = set()
    for path in glob.glob(os.path.join(datapath, "*.csv")):
        name = os.path.basename(path)
        parts = name.split("_")
        if len(parts) < 3:
            continue
        codes.add("_".join(parts[1:-1]))

    return sorted(codes)


def has_contract_prices(instrument_code: str) -> bool:
    return bool(glob.glob(f"{CP_PATH}/{instrument_code}#*.parquet"))


def backfill(instrument_code: str, datapath: str) -> dict:
    init_db_with_split_freq_csv_prices_for_code(
        instrument_code, datapath=datapath, csv_config=BARCHART_CONFIG
    )
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
        instrument_code, MERGE_FLAG=False, ADD_TO_DB=True
    )
    process_adjusted_prices_single_instrument(
        instrument_code, ADD_TO_DB=True, MERGE_ADJUSTED_PRICES=False
    )

    contracts = glob.glob(f"{CP_PATH}/{instrument_code}#*.parquet")
    adjusted_path = f"/Users/henrik/data/parquet/futures_adjusted_prices/{instrument_code}.parquet"
    adjusted = pd.read_parquet(adjusted_path)

    return dict(
        contracts=len(contracts),
        adjusted_rows=len(adjusted),
        first_date=str(adjusted.index[0].date()),
        last_date=str(adjusted.index[-1].date()),
    )


def main():
    parser = argparse.ArgumentParser(description="批量补全 Barchart 品种")
    parser.add_argument("--datapath", default="/private/tmp/barchart_all/barchart")
    parser.add_argument("--report", default="docs/backfill_report.csv")
    parser.add_argument("--force", action="store_true", help="已有合约价格也重新导入")
    args = parser.parse_args()

    fixed = normalise_headers(args.datapath)
    print(f"表头规范化：修改 {fixed} 个文件", flush=True)

    configured = set(pd.read_csv(INSTRUMENT_CONFIG)["Instrument"])
    targets = [
        code
        for code in instruments_in_backup(args.datapath)
        if code in configured
        and not has_contract_prices(code) or (args.force and code in configured)
    ]
    print(f"待处理品种：{len(targets)}", flush=True)

    rows = []
    for index, instrument_code in enumerate(targets, start=1):
        print(f"[{index}/{len(targets)}] {instrument_code}", flush=True)
        row = dict(instrument=instrument_code, status="OK")
        try:
            row.update(backfill(instrument_code, args.datapath))
        except Exception as error:  # 单个品种失败不阻断整批
            row["status"] = f"FAILED: {type(error).__name__}: {error}"[:200]
            print(f"    {row['status']}", flush=True)
        rows.append(row)
        pd.DataFrame(rows).to_csv(args.report, index=False)

    print("完成", flush=True)


if __name__ == "__main__":
    main()
