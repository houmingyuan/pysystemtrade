"""
把 Norgate 导出的历史（≤2026-09-18）并回「合并文件」，修 FIR-137 造成的历史覆盖。

⚠️ 一次性脚本：**已于 2026-09-27 执行完毕**，不要重复运行
   （再跑一次会重复并入同一批 Norgate 历史，没有意义）。

背景：
    上游的 IB 增量写入会重建合并文件（`write_merged_prices_for_contract` 用分频文件覆盖），
    对「历史只存在于合并文件」（没有 Day@ / Hour@）的合约，Norgate 导入的历史会被整段丢掉。
    实测 250 个合约的库内起点晚于 Norgate 导出起点（PLAT#20261000 只剩 166 行，
    Norgate 有 727 行），直接后果是换月日两侧合约没有重叠行情、日历构建被截断
    （PLAT / SILVER 的 multiple prices 停在 2026-07-29 就是这个原因）。

做法：
    * Norgate 行（时间戳 00:00）作为 ≤2026-09-18 的基准，全部并回；
    * 库内「日期 > 2026-09-18」的行（IB 增量）原样保留；
    * 同一天两边都有时保留 Norgate 那一行（先按索引排序，同日只留最早时间戳）。

默认 dry-run。用法：
    python sysinit/henrik/restore_norgate_history_into_merged.py            # 只报告
    python sysinit/henrik/restore_norgate_history_into_merged.py --commit   # 写入
    python sysinit/henrik/restore_norgate_history_into_merged.py --commit --instruments PLAT SILVER
"""

import argparse
import glob
import os
import sys

import pandas as pd

from sysdata.parquet.parquet_access import write_parquet_atomically

NORGATE_DIR = "/Volumes/data/systrade/norgate_export"
STORE_DIR = "/Volumes/data/systrade/parquet/futures_contract_prices"
NORGATE_HISTORY_END = pd.Timestamp("2026-09-18")


def restore_contract(csv_path: str, commit: bool) -> dict:
    name = os.path.basename(csv_path)[:-4]
    if "_" not in name:
        return dict(skipped=True)
    instrument_code, contract_id = name.rsplit("_", 1)
    parquet_path = os.path.join(STORE_DIR, "%s#%s.parquet" % (instrument_code, contract_id))
    if not os.path.exists(parquet_path):
        return dict(skipped=True)

    norgate = pd.read_csv(csv_path, index_col="DATETIME", parse_dates=True)
    if len(norgate) == 0:
        return dict(skipped=True)
    norgate = norgate[["OPEN", "HIGH", "LOW", "FINAL", "VOLUME"]]

    stored = pd.read_parquet(parquet_path)
    stored_late = stored[pd.DatetimeIndex(stored.index).normalize() > NORGATE_HISTORY_END]

    merged = pd.concat([norgate, stored_late]).sort_index()
    merged = merged[~pd.DatetimeIndex(merged.index).normalize().duplicated(keep="first")]

    result = dict(
        instrument=instrument_code,
        contract=contract_id,
        rows_before=len(stored),
        first_before=str(pd.DatetimeIndex(stored.index)[0].date()) if len(stored) else "-",
        rows_after=len(merged),
        first_after=str(pd.DatetimeIndex(merged.index)[0].date()),
    )
    if len(merged) <= len(stored):
        result["status"] = "无需恢复"
        return result

    if commit:
        write_parquet_atomically(merged, parquet_path)
        result["status"] = "已恢复 +%d 行" % (len(merged) - len(stored))
    else:
        result["status"] = "[dry-run] 将恢复 +%d 行" % (len(merged) - len(stored))
    return result


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="把 Norgate 历史并回合并文件")
    parser.add_argument("--commit", action="store_true")
    parser.add_argument("--instruments", nargs="*", default=None)
    parser.add_argument("--min-lost-rows", type=int, default=5, help="只处理至少丢失这么多行的合约")
    args = parser.parse_args(argv)

    csv_paths = sorted(glob.glob(os.path.join(NORGATE_DIR, "*.csv")))
    wanted = {code.upper() for code in args.instruments} if args.instruments else None

    restored = 0
    restored_rows = 0
    results = []
    for csv_path in csv_paths:
        name = os.path.basename(csv_path)[:-4]
        if wanted is not None:
            instrument_code = name.rsplit("_", 1)[0]
            if instrument_code.upper() not in wanted:
                continue
        try:
            result = restore_contract(csv_path, commit=args.commit)
        except Exception as error:
            print("失败 %s: %s: %s" % (name, type(error).__name__, str(error)[:80]))
            continue
        if result.get("skipped"):
            continue
        lost = result["rows_after"] - result["rows_before"]
        if lost >= args.min_lost_rows:
            restored += 1
            restored_rows += lost
            results.append(result)

    results.sort(key=lambda item: item["rows_after"] - item["rows_before"], reverse=True)
    for result in results[:30]:
        print(
            "%-14s %-9s %5d → %5d 行 (%s → %s)  %s"
            % (
                result["instrument"],
                result["contract"],
                result["rows_before"],
                result["rows_after"],
                result["first_before"],
                result["first_after"],
                result["status"],
            )
        )

    print(
        "\n受影响合约 %d 个，共需恢复 %d 行%s"
        % (restored, restored_rows, "" if args.commit else "（dry-run，未写入）")
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
