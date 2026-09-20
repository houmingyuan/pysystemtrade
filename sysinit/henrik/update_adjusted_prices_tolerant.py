"""
容错版 adjusted prices 更新（本地新增文件，非上游内容）。

背景：
    上游 sysinit/futures/update_adjusted_prices.py 调用的
    process_adjusted_prices_all_instruments() 与 multiple prices 版本一样没有异常隔离，
    任一品种抛错即终止整轮。

本脚本：
    逐品种 try/except，单个品种失败不中断整轮，最后汇总失败清单。

用法：
    python sysinit/henrik/update_adjusted_prices_tolerant.py
    python sysinit/henrik/update_adjusted_prices_tolerant.py BONO AUDJPY
"""

import sys
import traceback

from syscore.constants import arg_not_supplied
from sysinit.futures.adjustedprices_from_db_multiple_to_db import (
    process_adjusted_prices_single_instrument,
)
from sysproduction.data.prices import diagPrices


def _get_instrument_list(requested):
    if requested:
        return list(requested)
    diag_prices = diagPrices()
    return diag_prices.db_futures_multiple_prices_data.get_list_of_instruments()


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    allow_failures = "--allow-failures" in argv
    argv = [a for a in argv if not a.startswith("--")]
    instrument_list = _get_instrument_list(argv)
    total = len(instrument_list)

    print("=" * 70)
    print("容错版 adjusted prices 更新：共 %d 个品种" % total)
    print("=" * 70)

    succeeded, failed = [], []

    for i, instrument_code in enumerate(instrument_list, 1):
        prefix = "[%d/%d] %s" % (i, total, instrument_code)
        print("%s ..." % prefix)
        sys.stdout.flush()
        try:
            process_adjusted_prices_single_instrument(
                instrument_code,
                csv_adj_data_path=arg_not_supplied,
                ADD_TO_DB=True,
                ADD_TO_CSV=False,
                MERGE_ADJUSTED_PRICES=True,
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
