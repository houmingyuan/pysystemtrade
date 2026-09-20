"""
容错版 multiple prices 更新（本地新增文件，非上游内容）。

背景：
    上游 sysinit/futures/update_multiple_prices.py 调用的
    process_multiple_prices_all_instruments() 没有异常隔离，
    任一品种抛错（如 roll calendar 陈旧导致 "Empty roll calendar after adjustment"）
    即终止整轮，剩余品种全部得不到更新。

本脚本：
    逐品种 try/except，单个品种失败不中断整轮，最后汇总失败清单。

用法：
    python sysinit/henrik/update_multiple_prices_tolerant.py
    python sysinit/henrik/update_multiple_prices_tolerant.py SP500 AUDJPY
"""

import sys
import traceback

from syscore.constants import arg_not_supplied
from sysinit.futures.multipleprices_from_db_prices_and_csv_calendars_to_db import (
    process_multiple_prices_single_instrument,
)
from sysproduction.data.prices import diagPrices


def _get_instrument_list(requested):
    if requested:
        return list(requested)
    diag_prices = diagPrices()
    db_prices = diag_prices.db_futures_contract_price_data
    return db_prices.get_list_of_instrument_codes_with_merged_price_data()


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    allow_failures = "--allow-failures" in argv
    argv = [a for a in argv if not a.startswith("--")]
    instrument_list = _get_instrument_list(argv)
    total = len(instrument_list)

    print("=" * 70)
    print("容错版 multiple prices 更新：共 %d 个品种" % total)
    print("=" * 70)

    succeeded, failed = [], []

    for i, instrument_code in enumerate(instrument_list, 1):
        prefix = "[%d/%d] %s" % (i, total, instrument_code)
        print("%s ..." % prefix)
        sys.stdout.flush()
        try:
            process_multiple_prices_single_instrument(
                instrument_code,
                csv_multiple_data_path=arg_not_supplied,
                csv_roll_data_path=arg_not_supplied,
                MERGE_FLAG=True,
            )
        except Exception as exc:
            failed.append((instrument_code, "%s: %s" % (type(exc).__name__, exc)))
            print("%s FAILED -> %s: %s" % (prefix, type(exc).__name__, exc))
            print(traceback.format_exc())
        else:
            succeeded.append(instrument_code)
            print("%s OK" % prefix)
        sys.stdout.flush()

    print("=" * 70)
    print("成功 %d / %d" % (len(succeeded), total))
    if failed:
        print("失败 %d 个：" % len(failed))
        for code, err in failed:
            print("  - %s : %s" % (code, err))
    else:
        print("无失败")
    print("=" * 70)

    if not failed:
        return 0
    if allow_failures and succeeded:
        print("（--allow-failures：存在失败品种，但不阻断下游步骤）")
        return 0
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
