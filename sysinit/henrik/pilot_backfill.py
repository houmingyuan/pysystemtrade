#!/usr/bin/env python
"""
数据补全试点 / 批量导入：Barchart CSV -> 合约价格 -> 换月日历 -> multiple -> adjusted。

只对「Barchart 有、Norgate 没有」的品种使用（Norgate 已覆盖的品种不做处理）。
每一步可单独执行，便于分批验证与回滚。

用法：

    # 只导入合约价格（写入 parquet 合约价格库）
    python3 sysinit/henrik/pilot_backfill.py --instrument V2X \
        --datapath /private/tmp/barchart_pilot/barchart --steps prices

    # 继续生成换月日历 / multiple / adjusted
    python3 sysinit/henrik/pilot_backfill.py --instrument V2X --steps roll multiple adjusted
"""

import argparse

from syscore.constants import arg_not_supplied
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
from sysinit.futures.rollcalendars_from_db_prices_to_csv import (
    build_and_write_roll_calendar,
)

BARCHART_CONFIG = ConfigCsvFuturesPrices(
    input_date_index_name="Time",
    input_skiprows=0,
    input_skipfooter=0,
    input_date_format="%Y-%m-%dT%H:%M:%S%z",
    input_column_mapping=dict(
        OPEN="Open", HIGH="High", LOW="Low", FINAL="Close", VOLUME="Volume"
    ),
)

ALL_STEPS = ("prices", "roll", "multiple", "adjusted")


def run_instrument(
    instrument_code: str, datapath: str, steps: tuple, merge: bool = True
) -> None:
    print(f"\n===== {instrument_code}：{', '.join(steps)} =====")

    if "prices" in steps:
        init_db_with_split_freq_csv_prices_for_code(
            instrument_code, datapath=datapath, csv_config=BARCHART_CONFIG
        )

    if "roll" in steps:
        build_and_write_roll_calendar(
            instrument_code,
            output_datapath=arg_not_supplied,
            write=True,
            check_before_writing=False,
        )

    if "multiple" in steps:
        process_multiple_prices_single_instrument(
            instrument_code, MERGE_FLAG=merge, ADD_TO_DB=True
        )

    if "adjusted" in steps:
        process_adjusted_prices_single_instrument(
            instrument_code, ADD_TO_DB=True, MERGE_ADJUSTED_PRICES=merge
        )

    print(f"===== {instrument_code} 完成：{', '.join(steps)} =====")


def main():
    parser = argparse.ArgumentParser(description="Barchart CSV 导入链路")
    parser.add_argument("--instrument", nargs="+", required=True)
    parser.add_argument(
        "--datapath",
        default="/private/tmp/barchart_pilot/barchart",
        help="解包后的 Barchart CSV 目录",
    )
    parser.add_argument(
        "--steps",
        nargs="+",
        default=list(ALL_STEPS),
        choices=list(ALL_STEPS),
        help="执行哪些步骤（默认全部）",
    )
    parser.add_argument(
        "--no-merge",
        action="store_true",
        help="新品种首次构建时使用（与已有数据合并会因文件不存在而报错）",
    )
    args = parser.parse_args()

    for instrument_code in args.instrument:
        run_instrument(
            instrument_code,
            args.datapath,
            tuple(args.steps),
            merge=not args.no_merge,
        )


if __name__ == "__main__":
    main()
