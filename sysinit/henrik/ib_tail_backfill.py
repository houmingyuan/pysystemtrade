#!/usr/bin/env python
"""
IB 尾部补数：把新品种从「备份内容截止日」接到最新。

每个品种的处理顺序：
    a. 读 adjusted prices 最后日期（= 备份内容截止日）
    b. 从 IB 取合约列表（含已到期）
    c. 只补截止日往前 2 个月之后的合约，避免把十年历史全部重拉
    d. seed_price_data_for_contract 拉小时线 + 日线并合并入库
    e. 重建 multiple / adjusted（merge=True）

用法：
    python3 sysinit/henrik/ib_tail_backfill.py --instruments V2X CHEESE
    python3 sysinit/henrik/ib_tail_backfill.py --instruments-file docs/backfill_report.csv
"""

import argparse
import subprocess

import pandas as pd

from sysdata.data_blob import dataBlob
from sysobjects.contracts import futuresContract
from sysproduction.data.broker import dataBroker
from sysinit.futures.seed_price_data_from_IB import seed_price_data_for_contract
from sysinit.futures.adjustedprices_from_db_multiple_to_db import (
    process_adjusted_prices_single_instrument,
)
from sysinit.futures.multipleprices_from_db_prices_and_csv_calendars_to_db import (
    process_multiple_prices_single_instrument,
)

ADJUSTED_PATH = "/Users/henrik/data/parquet/futures_adjusted_prices"


def last_date_for(instrument_code: str):
    adjusted = pd.read_parquet(f"{ADJUSTED_PATH}/{instrument_code}.parquet")

    return adjusted.index[-1]


def contracts_to_seed(data_broker, instrument_code: str, start_date) -> list:
    contract_dates = data_broker.get_list_of_contract_dates_for_instrument_code(
        instrument_code, allow_expired=True
    )
    cutoff = start_date - pd.DateOffset(months=2)
    wanted = []
    for contract_date in contract_dates:
        date_str = contract_date[:6]
        try:
            contract_start = pd.Timestamp(f"{date_str[:4]}-{date_str[4:6]}-01")
        except Exception:
            continue
        if contract_start >= cutoff:
            wanted.append(date_str)

    return sorted(set(wanted))


def backfill(instrument_code: str, max_contracts: int = 0) -> str:
    data = dataBlob()
    data_broker = dataBroker(data)
    last_date = last_date_for(instrument_code)
    contracts = contracts_to_seed(data_broker, instrument_code, last_date)
    if max_contracts:
        contracts = contracts[-max_contracts:]

    seeded = 0
    for date_str in contracts:
        contract = futuresContract(instrument_code, date_str)
        try:
            seed_price_data_for_contract(data=data, contract_object=contract)
            seeded += 1
        except Exception as error:
            print(
                f"  {instrument_code} {date_str} 失败: {type(error).__name__}",
                flush=True,
            )

    # 拉完新合约后必须重建换月日历：旧日历的前端合约已到期，
    # 不重建的话 multiple prices 仍会停在备份截止日。
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

    return (
        f"{instrument_code}: 原截止 {last_date.date()}，补 {seeded} 个合约，"
        f"新截止 {last_date_for(instrument_code).date()}"
    )


def main():
    parser = argparse.ArgumentParser(description="IB 尾部补数")
    parser.add_argument("--instruments", nargs="*", default=[])
    parser.add_argument("--instruments-file", default=None)
    parser.add_argument(
        "--max-contracts", type=int, default=0, help="每品种最多补多少合约（0=不限）"
    )
    args = parser.parse_args()

    instruments = list(args.instruments)
    if args.instruments_file:
        report = pd.read_csv(args.instruments_file)
        instruments += report.instrument.tolist()
    instruments = sorted(set(instruments))
    print(f"待补尾部品种 {len(instruments)} 个", flush=True)

    for instrument_code in instruments:
        try:
            print(backfill(instrument_code, args.max_contracts), flush=True)
        except Exception as error:
            print(
                f"{instrument_code}: 失败 {type(error).__name__}: {str(error)[:120]}",
                flush=True,
            )


if __name__ == "__main__":
    main()
