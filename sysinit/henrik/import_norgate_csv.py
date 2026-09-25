"""
把 Norgate 导出的逐合约 CSV 导入生产 Parquet 存储。

与上游 sysinit/futures/contract_prices_from_csv_to_db.py 的差别：
1. 解析配置匹配 Norgate 的列名（DATETIME / OPEN / HIGH / LOW / FINAL / VOLUME）与日期格式
2. 对 SILVER 与 COPPER 做单位换算：Norgate 用美分计价（美分/盎司、美分/磅），
   IB 用美元计价，已用 IB 实测确认存在 100 倍差异。这里除以 100 统一到 IB 的美元口径，
   与 ib_config_futures.csv 中 priceMagnifier=1、instrumentconfig 中 SILVER 1000、
   COPPER 25000 的现有配置自洽。
3. 只导入 instrumentconfig.csv 中存在的品种，其余（AUS10、AUS3、AUS_BILL90）自动跳过

用法：
    python sysinit/henrik/import_norgate_csv.py --dry-run          # 只列出将要导入的品种
    python sysinit/henrik/import_norgate_csv.py --limit 3          # 先试三个品种
    python sysinit/henrik/import_norgate_csv.py                    # 全量导入
"""

import argparse
import glob
import os
import shutil
import sys

import pandas as pd

from syscore.dateutils import MIXED_FREQ, replace_midnight_with_notional_closing_time
from syscore.fileutils import resolve_path_and_filename_for_package
from sysdata.csv.csv_futures_contract_prices import (
    ConfigCsvFuturesPrices,
    csvFuturesContractPriceData,
)
from sysobjects.contracts import futuresContract
from sysobjects.futures_per_contract_prices import futuresContractPrices
from sysproduction.data.prices import diagPrices

NORGATE_DIR = "/Volumes/data/systrade/norgate_export"
PREPARED_DIR = "/Volumes/data/systrade/norgate_export_usd"

# 需要从美分换算为美元的品种（IB 实测确认 100 倍差异）
CENTS_TO_DOLLARS = ("SILVER", "COPPER")

NORGATE_CSV_CONFIG = ConfigCsvFuturesPrices(
    input_date_index_name="DATETIME",
    input_skiprows=0,
    input_skipfooter=0,
    input_date_format="%Y-%m-%d",
    input_column_mapping=dict(
        OPEN="OPEN", HIGH="HIGH", LOW="LOW", FINAL="FINAL", VOLUME="VOLUME"
    ),
)

diag_prices = diagPrices()


def apply_pst_daily_convention(
    prices_for_contract: futuresContractPrices,
) -> futuresContractPrices:
    """
    把日线时间戳从 00:00 规范到 PST 的日线约定（notional closing time，即当日 23:00）。

    Norgate 导出的 DATETIME 只有日期，直接解析会得到 00:00；而 PST 自带 CSV 与 IB 取数
    路径（ib_price_client._ib_timestamp_to_datetime）用的都是 23:00。两者混在一个品种里
    会导致换月匹配（需要同日同时间戳）永远失败，进而让 roll calendar 被静默截断、
    前端合约停在过期合约上（FIR-131）。
    """
    prices_as_df = pd.DataFrame(prices_for_contract).copy()
    original_index = prices_as_df.index
    prices_as_df.index = [
        replace_midnight_with_notional_closing_time(timestamp)
        for timestamp in original_index
    ]
    duplicates = int(prices_as_df.index.duplicated(keep="last").sum())
    if duplicates:
        prices_as_df = prices_as_df[~prices_as_df.index.duplicated(keep="last")]

    return futuresContractPrices(prices_as_df)


def import_instrument(code: str, datapath: str, frequency=MIXED_FREQ) -> int:
    """
    与上游 init_db_with_csv_futures_contract_prices_for_code 相同，只是在写库前把
    日线时间戳规范到 PST 约定的 23:00。
    """
    csv_prices = csvFuturesContractPriceData(datapath, config=NORGATE_CSV_CONFIG)
    db_prices = diag_prices.db_futures_contract_price_data

    csv_price_dict = csv_prices.get_prices_at_frequency_for_instrument(
        code, frequency
    )

    for contract_date_str, prices_for_contract in csv_price_dict.items():
        prices_for_contract = apply_pst_daily_convention(prices_for_contract)
        contract = futuresContract(code, contract_date_str)
        db_prices.write_prices_at_frequency_for_contract_object(
            contract,
            prices_for_contract,
            ignore_duplication=True,
            frequency=frequency,
        )

    return len(csv_price_dict)


def instruments_in_export() -> list:
    codes = set()
    for path in glob.glob(f"{NORGATE_DIR}/*.csv"):
        name = os.path.basename(path)[:-4]
        if "_" in name:
            codes.add(name.rsplit("_", 1)[0])
    return sorted(codes)


def known_instruments() -> set:
    instrument_config = pd.read_csv(
        resolve_path_and_filename_for_package(
            "data.futures.csvconfig", "instrumentconfig.csv"
        )
    )
    return set(instrument_config["Instrument"].astype(str))


def prepare_usd_copies(codes) -> None:
    """
    把需要换算的品种复制到 PREPARED_DIR，并把 OHLC 除以 100。
    """
    os.makedirs(PREPARED_DIR, exist_ok=True)
    for code in codes:
        for path in sorted(glob.glob(f"{NORGATE_DIR}/{code}_*.csv")):
            target = os.path.join(PREPARED_DIR, os.path.basename(path))
            if os.path.exists(target):
                continue
            df = pd.read_csv(path)
            for column in ["OPEN", "HIGH", "LOW", "FINAL"]:
                if column in df.columns:
                    df[column] = pd.to_numeric(df[column], errors="coerce") / 100.0
            df.to_csv(target, index=False)
        print(f"已换算为美元口径: {code}")


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true", help="只列出将要导入的品种")
    parser.add_argument("--limit", type=int, default=None, help="只导入前 N 个品种")
    parser.add_argument(
        "--skip-prepare", action="store_true", help="跳过美分到美元的换算准备"
    )
    args = parser.parse_args(argv)

    if not os.path.isdir(NORGATE_DIR):
        print(f"导出目录不存在: {NORGATE_DIR}")
        return 1

    known = known_instruments()
    all_codes = instruments_in_export()
    to_import = [c for c in all_codes if c in known]
    skipped = [c for c in all_codes if c not in known]

    print(f"导出品种数: {len(all_codes)}")
    print(f"将导入:     {len(to_import)}")
    print(f"跳过(不在 instrumentconfig): {skipped}")
    if args.limit:
        to_import = to_import[: args.limit]
        print(f"按 --limit 限制为: {to_import}")

    if args.dry_run:
        print("dry-run，未写入任何数据")
        return 0

    needs_conversion = [c for c in to_import if c in CENTS_TO_DOLLARS]
    if needs_conversion and not args.skip_prepare:
        prepare_usd_copies(needs_conversion)

    failures = []
    for index, code in enumerate(to_import, start=1):
        datapath = PREPARED_DIR if code in CENTS_TO_DOLLARS else NORGATE_DIR
        print(f"[{index}/{len(to_import)}] {code}  (来源 {datapath})", flush=True)
        try:
            contracts = import_instrument(code, datapath=datapath)
            print(f"  已导入 {contracts} 个合约（时间戳已规范为 23:00）", flush=True)
        except Exception as error:
            failures.append((code, f"{type(error).__name__}: {str(error)[:80]}"))
            print(f"  失败: {failures[-1][1]}", flush=True)

    print()
    print(f"完成，成功 {len(to_import) - len(failures)} / {len(to_import)}")
    if failures:
        print("失败清单:")
        for code, reason in failures:
            print(f"  {code}: {reason}")
    return 0 if not failures else 1


if __name__ == "__main__":
    sys.exit(main())
