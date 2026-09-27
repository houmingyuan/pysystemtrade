"""
FIR-127 只读归因：把每日更新中「价格尖峰被拒」的合约，重新从 IB 取一次数据与库内比对。

不写入任何数据；输出明细到 /tmp/fir127_spike_audit.csv，并在终端打印分类汇总。

用法：
    python sysinit/henrik/audit_ib_price_spikes.py                 # 解析最近一份更新日志里的被拒合约
    python sysinit/henrik/audit_ib_price_spikes.py --log /Volumes/data/systrade/log/update_20260924.log
    python sysinit/henrik/audit_ib_price_spikes.py --limit 20       # 先试前 20 个
    python sysinit/henrik/audit_ib_price_spikes.py --frequency both # 日线 + 小时线
"""

import argparse
import glob
import os
import re
import sys
from collections import Counter

import numpy as np
import pandas as pd

from syscore.constants import arg_not_supplied
from syscore.dateutils import DAILY_PRICE_FREQ
from syscore.pandas.merge_data_keeping_past_data import (
    NO_MERGE_DATE,
    merge_newer_data_no_checks,
)
from syscore.pandas.merge_data_keeping_past_data import (
    _calculate_change_in_vol_normalised_units,
)
from sysdata.data_blob import dataBlob
from sysobjects.contracts import futuresContract
from sysproduction.data.broker import dataBroker
from sysproduction.data.prices import diagPrices

DEFAULT_LOG_DIR = "/Volumes/data/systrade/log"
LOG_FILE_PATTERN = "update_*.log"
OUTPUT_CSV = "/tmp/fir127_spike_audit.csv"
MAX_PRICE_SPIKE = 8.0

LOG_PATTERN = re.compile(
    r"instrument_code': '([^']+)', 'contract_date': '([^']+)'.*moved too much"
)


def latest_update_log(log_dir: str = DEFAULT_LOG_DIR) -> str:
    """不指定 --log 时用最近一份 update_*.log，不再硬编码某一天。"""
    candidates = sorted(glob.glob(os.path.join(log_dir, LOG_FILE_PATTERN)))
    if not candidates:
        raise SystemExit(
            "在 %s 下找不到 %s，请用 --log 指定要审计的日志" % (log_dir, LOG_FILE_PATTERN)
        )

    return candidates[-1]


def rejected_contracts_from_log(path: str) -> list:
    pairs = []
    for line in open(path, errors="ignore"):
        match = LOG_PATTERN.search(line)
        if match:
            pairs.append((match.group(1), match.group(2)))
    # 去重但保留顺序
    seen = set()
    ordered = []
    for pair in pairs:
        if pair not in seen:
            seen.add(pair)
            ordered.append(pair)
    return ordered


def audit_one(data, instrument_code: str, contract_date_str: str, frequency) -> dict:
    row = dict(
        instrument=instrument_code,
        contract=contract_date_str,
        frequency=str(frequency),
        stored_last_date="",
        stored_last_price=np.nan,
        ib_rows=0,
        ib_first_new_date="",
        ib_first_new_price=np.nan,
        ib_last_date="",
        ib_last_price=np.nan,
        new_rows_vs_store=0,
        spike_ratio=np.nan,
        spike_date="",
        price_before=np.nan,
        price_at_spike=np.nan,
        pct_change=np.nan,
        storage="按频率文件",
        verdict="",
        note="",
    )

    broker = dataBroker(data)
    diag = diagPrices(data)
    contract = futuresContract(instrument_code, contract_date_str)

    try:
        raw_ib = broker.get_prices_at_frequency_for_contract_object(
            contract_object=contract, frequency=frequency
        )
    except Exception as error:
        row["verdict"] = "IB 取数失败"
        row["note"] = f"{type(error).__name__}: {str(error)[:120]}"
        return row

    if raw_ib is None or len(raw_ib) == 0:
        row["verdict"] = "IB 无数据"
        return row

    ib_frame = pd.DataFrame(raw_ib)
    ib_frame = ib_frame[~ib_frame.index.duplicated(keep="last")].sort_index()
    row["ib_rows"] = len(ib_frame)
    row["ib_first_new_date"] = str(ib_frame.index[0])
    row["ib_first_new_price"] = float(ib_frame["FINAL"].iloc[0])
    row["ib_last_date"] = str(ib_frame.index[-1])
    row["ib_last_price"] = float(ib_frame["FINAL"].iloc[-1])

    try:
        stored = diag.get_prices_at_frequency_for_contract_object(
            contract, frequency=frequency
        )
    except Exception as error:
        row["verdict"] = "库内读取失败"
        row["note"] = f"{type(error).__name__}: {str(error)[:120]}"
        return row

    if stored is None or len(stored) == 0:
        # 频率文件为空：PST 会把整段新数据都当作要检查（NEW_DATA_ONLY）
        stored_frame = pd.DataFrame(
            columns=ib_frame.columns, index=pd.DatetimeIndex([])
        )
        row["storage"] = "频率文件为空（整段新数据检查）"
        stored_last = None
    else:
        stored_frame = pd.DataFrame(stored)
        stored_frame = stored_frame[
            ~stored_frame.index.duplicated(keep="last")
        ].sort_index()
        row["stored_last_date"] = str(stored_frame.index[-1])
        row["stored_last_price"] = float(stored_frame["FINAL"].iloc[-1])
        stored_last = stored_frame.index[-1]

    if stored_last is None:
        newer_bars = ib_frame
    else:
        newer_bars = ib_frame[ib_frame.index > stored_last]
    row["new_rows_vs_store"] = len(newer_bars)
    if len(newer_bars) == 0 and stored_last is not None:
        row["verdict"] = "IB 没有比库内更新的数据"
        return row

    # 完全按 PST 的判定复现：把旧数据与新数据合起来，算「波动归一化后的变动」，
    # 只看合并点之后的数据；> max_spike 即为尖峰。
    merged_with_status = merge_newer_data_no_checks(stored_frame, ib_frame)
    merged = merged_with_status.merged_data
    join_date = merged_with_status.date_of_merge_join

    normalised = _calculate_change_in_vol_normalised_units(merged["FINAL"])
    if join_date is NO_MERGE_DATE:
        relevant = normalised
        row["storage"] = "旧数据为空（整段新数据都检查）"
    else:
        relevant = normalised[normalised.index > join_date]
    if len(relevant) == 0:
        row["verdict"] = "新数据不足两点，无法判定"
        return row

    spike_date = relevant.idxmax()
    row["spike_ratio"] = float(relevant.max())
    row["spike_date"] = str(spike_date)
    price_before = float(merged["FINAL"].loc[:spike_date].iloc[-2])
    price_at_spike = float(merged["FINAL"].loc[spike_date])
    row["price_before"] = price_before
    row["price_at_spike"] = price_at_spike
    row["pct_change"] = 100.0 * (price_at_spike - price_before) / price_before

    price_ratio = price_at_spike / price_before if price_before else np.nan
    if 90 <= price_ratio <= 110 or 0.009 <= price_ratio <= 0.011:
        row["verdict"] = "疑似单位/口径差异（约 100 倍）"
    elif row["spike_ratio"] > MAX_PRICE_SPIKE:
        row["verdict"] = "尖峰成立"
    else:
        row["verdict"] = "未超阈值（不应被拒）"

    return row


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="FIR-127 尖峰拒绝只读归因")
    parser.add_argument(
        "--log", default=None, help="要审计的更新日志，默认取最近一份 update_*.log"
    )
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument(
        "--frequency",
        choices=["daily", "both"],
        default="daily",
        help="daily=只查日线（默认），both=日线+小时线",
    )
    args = parser.parse_args(argv)

    log_path = args.log or latest_update_log()
    pairs = rejected_contracts_from_log(log_path)
    if args.limit:
        pairs = pairs[: args.limit]
    print(f"被拒合约（去重）{len(pairs)} 个，来源 {log_path}", flush=True)

    with dataBlob(log_name="Price-Spike-Audit") as data:
        frequencies = [DAILY_PRICE_FREQ]
        if args.frequency == "both":
            frequencies.append(
                diagPrices(data).get_intraday_frequency_for_historical_download()
            )

        rows = []
        for position, (instrument_code, contract_date_str) in enumerate(pairs, start=1):
            for frequency in frequencies:
                try:
                    rows.append(
                        audit_one(data, instrument_code, contract_date_str, frequency)
                    )
                except Exception as error:  # 单个合约失败不影响其余
                    rows.append(
                        dict(
                            instrument=instrument_code,
                            contract=contract_date_str,
                            frequency=str(frequency),
                            verdict="审计异常",
                            note=f"{type(error).__name__}: {str(error)[:120]}",
                        )
                    )
            if position % 20 == 0:
                print(f"  已完成 {position}/{len(pairs)}", flush=True)

    result = pd.DataFrame(rows)
    result.to_csv(OUTPUT_CSV, index=False)
    print(f"\n明细写入 {OUTPUT_CSV}")
    print("\n分类汇总：")
    for verdict, count in Counter(result["verdict"]).most_common():
        print(f"  {verdict}: {count}")

    spikes = result[result["verdict"] == "尖峰成立"]
    if len(spikes):
        print("\n尖峰成立（按归一化变动降序，前 20）：")
        cols = [
            "instrument",
            "contract",
            "storage",
            "spike_date",
            "price_before",
            "price_at_spike",
            "pct_change",
            "spike_ratio",
        ]
        print(
            spikes.sort_values("spike_ratio", ascending=False)[cols]
            .head(20)
            .to_string(index=False)
        )

    return 0


if __name__ == "__main__":
    sys.exit(main())
