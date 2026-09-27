"""
回滚 FIR-131 的「时间戳口径统一」：把 Norgate 日线的 23:00 改回导出时的 00:00（FIR-144）。

⚠️ 一次性脚本：**已于 2026-09-27 执行完毕**，不要重复运行
   （再跑一次会拿旧备份去比对已经改好的数据，属于无意义操作）。

背景：2026-09-25 的 FIR-131 主线把全库合约价格文件的日线时间戳从 Norgate 导出的
00:00 统一改写成 PST 约定的 23:00（当次记录：23,223 个文件、9,820,442 行）。
本脚本用那次改动前的备份做逐文件比对，只把「备份里是 00:00、库内是 23:00」的行改回
00:00；备份里本来就是 23:00 的行（IB 来源）与改动之后新增的行保持不动。

依赖的备份（不要删除）：
    /Users/henrik/data/backup/fir131_before_timestamp_fix_20260925/futures_contract_prices

用法：
    python sysinit/henrik/rollback_norgate_timestamps.py --dry-run     # 只统计
    python sysinit/henrik/rollback_norgate_timestamps.py               # 全量回滚
    python sysinit/henrik/rollback_norgate_timestamps.py --limit 100   # 先试 100 个文件
"""

import argparse
import os
import sys

import pandas as pd

from sysdata.parquet.parquet_access import write_parquet_atomically

CURRENT_DIR = "/Volumes/data/systrade/parquet/futures_contract_prices"
BACKUP_DIR = (
    "/Users/henrik/data/backup/fir131_before_timestamp_fix_20260925"
    "/futures_contract_prices"
)

MIDNIGHT = pd.Timestamp("2000-01-01 00:00:00").time()
NOTIONAL_CLOSE = pd.Timestamp("2000-01-01 23:00:00").time()


def dates_with_midnight_timestamp(prices: pd.DataFrame) -> set:
    """备份里以 00:00 开头的日期集合，即 Norgate 原始日线。"""
    index = pd.DatetimeIndex(prices.index)
    return set(index[index.time == MIDNIGHT].normalize())


def revert_file(filename: str, dry_run: bool = False) -> dict:
    """把单个合约文件里「原为 00:00、已被改成 23:00」的行改回 00:00。"""
    current_path = os.path.join(CURRENT_DIR, filename)
    backup_path = os.path.join(BACKUP_DIR, filename)
    result = dict(filename=filename, changed_rows=0, dropped_duplicates=0, skipped=None)

    if not os.path.exists(backup_path):
        result["skipped"] = "备份里没有这个文件（改动后新增）"
        return result

    current = pd.read_parquet(current_path)
    backup = pd.read_parquet(backup_path)
    norgate_dates = dates_with_midnight_timestamp(backup)
    if not norgate_dates:
        result["skipped"] = "备份里没有 00:00 的行"
        return result

    index = pd.DatetimeIndex(current.index)
    mask = index.normalize().isin(norgate_dates) & (index.time == NOTIONAL_CLOSE)
    if not mask.any():
        result["skipped"] = "没有需要回退的 23:00 行"
        return result

    values = index.values.copy()
    values[mask] = values[mask].astype("datetime64[D]").astype(values.dtype)
    reverted = pd.DataFrame(current)
    reverted.index = pd.DatetimeIndex(values)

    duplicates = int(reverted.index.duplicated(keep="last").sum())
    if duplicates:
        # 回退后若与已有 00:00 行撞车，保留后写入的一条，行为与当初的规范化一致
        reverted = reverted[~reverted.index.duplicated(keep="last")]

    result["changed_rows"] = int(mask.sum())
    result["dropped_duplicates"] = duplicates

    if not dry_run:
        write_parquet_atomically(reverted, current_path)

    return result


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="回滚 Norgate 日线时间戳 23:00 → 00:00")
    parser.add_argument("--dry-run", action="store_true", help="只统计，不写盘")
    parser.add_argument("--limit", type=int, default=None, help="只处理前 N 个文件")
    parser.add_argument(
        "--instruments",
        nargs="*",
        default=None,
        help="只处理这些品种（按文件名前缀匹配）",
    )
    args = parser.parse_args(argv)

    if not os.path.isdir(CURRENT_DIR):
        print(f"合约价格库不存在: {CURRENT_DIR}")
        return 1
    if not os.path.isdir(BACKUP_DIR):
        print(f"FIR-131 备份不存在: {BACKUP_DIR}")
        return 1

    filenames = sorted(os.listdir(CURRENT_DIR))
    if args.instruments:
        wanted = {code.upper() for code in args.instruments}
        filenames = [
            name for name in filenames if name.split("#")[0].upper() in wanted
        ]
    if args.limit:
        filenames = filenames[: args.limit]

    print(
        f"{'[dry-run] ' if args.dry_run else ''}待处理文件 {len(filenames)} 个"
        "（逐文件与 FIR-131 备份比对）",
        flush=True,
    )

    changed_files = 0
    changed_rows = 0
    dropped_duplicates = 0
    failures = []
    for position, filename in enumerate(filenames, start=1):
        try:
            result = revert_file(filename, dry_run=args.dry_run)
        except Exception as error:  # 单个文件失败不影响其余
            failures.append((filename, f"{type(error).__name__}: {str(error)[:120]}"))
            continue
        if result["changed_rows"]:
            changed_files += 1
            changed_rows += result["changed_rows"]
            dropped_duplicates += result["dropped_duplicates"]
        if position % 2000 == 0:
            print(
                f"  已处理 {position}/{len(filenames)}，"
                f"已回退 {changed_files} 个文件 / {changed_rows} 行",
                flush=True,
            )

    print(
        f"完成：{changed_files} 个文件、{changed_rows} 行由 23:00 改回 00:00"
        f"（顺带去掉重复时间戳 {dropped_duplicates} 行）"
    )
    if failures:
        print(f"失败 {len(failures)} 个文件：")
        for filename, message in failures[:20]:
            print(f"  {filename}: {message}")
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
