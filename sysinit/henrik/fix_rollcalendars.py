"""
从价格数据重建指定品种的 roll calendar（本地新增文件，非上游内容）。

场景：
    data/futures/roll_calendars_csv/<INSTRUMENT>.csv 与可用价格区间不重叠
    （典型：日历停在 2016~2022，而 barchart 价格从 2023/2024 才开始），
    导致 update_multiple_prices.py 抛：
        Exception: Error! Empty roll calendar after adjustment!

行为：
    1. 备份原 calendar 到 roll_calendars_csv/backup/<YYYYMMDD-HHMMSS>/
    2. 用合约价格推断日历（rollCalendar.create_from_prices），写到 roll_calendars_csv/new/
    3. 按模式回写主目录：
         --merge    （默认）保留已有行，仅补充新行：按 current_contract 去重，已存在的优先
         --replace  整体替换为价格推断出的日历

    默认 merge 更保守：不会覆盖已有的权威 roll 日期，只把缺失的补上。

用法：
    python sysinit/henrik/fix_rollcalendars.py --dry-run BONO
    python sysinit/henrik/fix_rollcalendars.py BONO AUDJPY BB3M
    python sysinit/henrik/fix_rollcalendars.py --replace BONO
"""

import os
import shutil
import sys
from datetime import datetime

import pandas as pd

from sysinit.futures.rollcalendars_from_db_prices_to_csv import (
    build_and_write_roll_calendar,
)

ROLL_CALENDAR_DIR = "/Users/henrik/dev/pysystemtrade/data/futures/roll_calendars_csv"
NEW_CALENDAR_DIR = os.path.join(ROLL_CALENDAR_DIR, "new")

COLUMNS = ["DATE_TIME", "current_contract", "next_contract", "carry_contract"]


def _backup(instrument_code, stamp):
    src = os.path.join(ROLL_CALENDAR_DIR, instrument_code + ".csv")
    if not os.path.exists(src):
        return None
    backup_dir = os.path.join(ROLL_CALENDAR_DIR, "backup", stamp)
    os.makedirs(backup_dir, exist_ok=True)
    dst = os.path.join(backup_dir, instrument_code + ".csv")
    shutil.copy(src, dst)
    return dst


def _normalise_datetime(series):
    series = series.astype(str)
    return series.apply(lambda x: x if len(x) > 10 else x + " 00:00:00")


def _merge_into(input_path, dst_path):
    """保留已有行，补充新行；按 current_contract 去重（已存在的优先）"""
    new_df = pd.read_csv(input_path)
    new_df["DATE_TIME"] = _normalise_datetime(new_df["DATE_TIME"])

    if os.path.exists(dst_path):
        dst_df = pd.read_csv(dst_path)
        dst_df["DATE_TIME"] = _normalise_datetime(dst_df["DATE_TIME"])
        before = len(dst_df)
        merged = pd.concat([dst_df, new_df], ignore_index=True)
        merged = merged.drop_duplicates(subset=["current_contract"], keep="first")
        merged = merged.sort_values(by=["DATE_TIME"], ascending=True)
        added = len(merged) - before
    else:
        merged = new_df.sort_values(by=["DATE_TIME"], ascending=True)
        added = len(merged)

    merged[COLUMNS].to_csv(dst_path, index=False)
    return len(merged), added


def _summarise(path):
    if not os.path.exists(path):
        return "(无文件)"
    df = pd.read_csv(path)
    if len(df) == 0:
        return "0 行"
    return "%d 行, 首=%s, 末=%s" % (
        len(df),
        str(df["DATE_TIME"].iloc[0])[:16],
        str(df["DATE_TIME"].iloc[-1])[:16],
    )


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    dry_run = "--dry-run" in argv
    replace = "--replace" in argv
    instrument_list = [a for a in argv if not a.startswith("--")]

    if not instrument_list:
        print(
            "用法: python sysinit/henrik/fix_rollcalendars.py "
            "[--dry-run] [--replace] <INSTRUMENT> [...]"
        )
        return 2

    mode = "replace（整体替换）" if replace else "merge（保留已有，补充新行）"
    print("模式: %s%s" % (mode, "  [DRY-RUN 不写入]" if dry_run else ""))
    print("品种: %s" % ", ".join(instrument_list))
    print("=" * 70)

    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    results = []

    for instrument_code in instrument_list:
        print("\n### %s" % instrument_code)
        dst_path = os.path.join(ROLL_CALENDAR_DIR, instrument_code + ".csv")
        new_path = os.path.join(NEW_CALENDAR_DIR, instrument_code + ".csv")
        print("原日历: %s" % _summarise(dst_path))

        try:
            build_and_write_roll_calendar(
                instrument_code,
                output_datapath=NEW_CALENDAR_DIR,
                write=not dry_run,
                check_before_writing=False,
            )
        except Exception as exc:
            print("构建失败 -> %s: %s" % (type(exc).__name__, exc))
            results.append((instrument_code, False, "%s: %s" % (type(exc).__name__, exc)))
            continue

        if dry_run:
            print("新日历(未写入): %s" % _summarise(new_path))
            results.append((instrument_code, True, "dry-run"))
            continue

        backup_path = _backup(instrument_code, stamp)
        print("备份: %s" % (backup_path or "(原文件不存在)"))

        if replace:
            shutil.copy(new_path, dst_path)
            detail = "替换为 %s" % _summarise(dst_path)
        else:
            total, added = _merge_into(new_path, dst_path)
            detail = "合并后 %d 行（新增 %d）" % (total, added)

        print("结果: %s" % detail)
        results.append((instrument_code, True, detail))

    print("\n" + "=" * 70)
    ok = sum(1 for _, success, _ in results if success)
    print("成功 %d / %d" % (ok, len(results)))
    for code, success, detail in results:
        print("  %s %s : %s" % ("OK  " if success else "FAIL", code, detail))

    return 0 if ok == len(results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
