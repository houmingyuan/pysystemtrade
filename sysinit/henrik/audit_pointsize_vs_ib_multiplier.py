"""
FIR-153：核对 `instrumentconfig.csv` 的 Pointsize 与 IB 配置的乘数是否一致。

PST 自己的规则（`interactive_controls.check_price_multipliers_consistent_for_instrument`，
其中 `IBconfig.effective_multiplier = IBMultiplier / priceMagnifier`）：

    Pointsize == IBMultiplier / priceMagnifier

本脚本对价格库里的品种逐个比对，输出不一致清单。只读。

用法：
    python sysinit/henrik/audit_pointsize_vs_ib_multiplier.py
    python sysinit/henrik/audit_pointsize_vs_ib_multiplier.py --all-configured
"""

import argparse
import os
import sys

import pandas as pd

INSTRUMENT_CONFIG = "data/futures/csvconfig/instrumentconfig.csv"
IB_CONFIG = "sysbrokers/IB/config/ib_config_futures.csv"
MULTIPLE_PRICES_DIR = "/Volumes/data/systrade/parquet/futures_multiple_prices"


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="核对 Pointsize 与 IB 乘数")
    parser.add_argument(
        "--all-configured",
        action="store_true",
        help="比对 IB 配置里的全部品种（默认只比对价格库里的品种）",
    )
    args = parser.parse_args(argv)

    instrument_config = pd.read_csv(INSTRUMENT_CONFIG).set_index("Instrument")
    ib_config = pd.read_csv(IB_CONFIG).set_index("Instrument")

    if args.all_configured:
        instruments = sorted(ib_config.index)
    else:
        instruments = sorted(
            filename[:-8] for filename in os.listdir(MULTIPLE_PRICES_DIR)
        )

    mismatches = []
    missing = []
    for instrument_code in instruments:
        if instrument_code not in instrument_config.index or instrument_code not in ib_config.index:
            missing.append(instrument_code)
            continue
        point_size = float(instrument_config.loc[instrument_code, "Pointsize"])
        ib_multiplier = float(ib_config.loc[instrument_code, "IBMultiplier"])
        price_magnifier = float(ib_config.loc[instrument_code, "priceMagnifier"])
        effective = ib_multiplier / price_magnifier if price_magnifier else float("nan")
        if abs(point_size - effective) > 1e-6:
            mismatches.append(
                (instrument_code, point_size, ib_multiplier, price_magnifier, effective)
            )

    print("比对品种 %d" % len(instruments))
    print("两边配置缺一方的 %d: %s" % (len(missing), missing[:20]))
    print("Pointsize != IBMultiplier / priceMagnifier 的 %d:" % len(mismatches))
    for instrument_code, point_size, ib_multiplier, price_magnifier, effective in mismatches:
        print(
            "   %-16s Pointsize=%-10s IBMultiplier=%-10s magnifier=%-6s → 期望 %s"
            % (instrument_code, point_size, ib_multiplier, price_magnifier, effective)
        )

    return 0


if __name__ == "__main__":
    sys.exit(main())
