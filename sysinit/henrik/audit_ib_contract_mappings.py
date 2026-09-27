"""
FIR-151：全库复核 IB 合约映射能否解析。

对 `sysbrokers/IB/config/ib_config_futures.csv` 里的每个品种，让 IB 返回它的可交易合约月份
（`get_list_of_contract_dates_for_instrument_code`）；解析失败或返回空的记入清单。

只读。用法：
    python sysinit/henrik/audit_ib_contract_mappings.py
    python sysinit/henrik/audit_ib_contract_mappings.py --instruments TSX WHEAT-ASX CRUDE_ICE
"""

import argparse
import sys

import pandas as pd

from syscore.constants import arg_not_supplied
from sysdata.data_blob import dataBlob
from sysproduction.data.broker import dataBroker

ROLL_CALENDAR_PATH = "data/futures/roll_calendars_csv"


def front_contract_month(instrument_code: str) -> str:
    """日历最后一行 next_contract 的月份（'YYYYMM'）；没有日历返回空串。"""
    import os

    path = os.path.join(ROLL_CALENDAR_PATH, "%s.csv" % instrument_code)
    if not os.path.exists(path):
        return ""
    try:
        calendar = pd.read_csv(path)
    except Exception:
        return ""
    if len(calendar) == 0:
        return ""
    return str(calendar.iloc[-1]["next_contract"])[:6]


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="复核 IB 合约映射")
    parser.add_argument("--instruments", nargs="*", default=None)
    parser.add_argument("--client-id", type=int, default=995)
    args = parser.parse_args(argv)

    with dataBlob(log_name="Audit-IB-Mappings") as data:
        broker_data = dataBroker(data).broker_futures_contract_data
        configured = sorted(
            pd.read_csv("sysbrokers/IB/config/ib_config_futures.csv")["Instrument"].tolist()
        )
        instruments = (
            sorted(set(args.instruments))
            if args.instruments
            else [c for c in configured if c and not c.startswith(" ")]
        )

        ok = []
        empty = []
        failed = []
        stale_front = []
        for instrument_code in instruments:
            try:
                dates = broker_data.get_list_of_contract_dates_for_instrument_code(
                    instrument_code, allow_expired=False
                )
            except Exception as error:
                failed.append((instrument_code, "%s: %s" % (type(error).__name__, str(error)[:70])))
                continue
            if not dates:
                empty.append(instrument_code)
                continue

            ok.append((instrument_code, str(dates[0]), len(dates)))
            front_month = front_contract_month(instrument_code)
            months = {str(entry)[:6] for entry in dates}
            if front_month and front_month not in months:
                stale_front.append((instrument_code, front_month, sorted(months)[:3]))

        print("品种总数 %d" % len(instruments))
        print("可解析 %d" % len(ok))
        print("返回空 %d: %s" % (len(empty), empty[:30]))
        print("日历前端已不在 IB 可交易月份 %d:" % len(stale_front))
        for instrument_code, front_month, sample in stale_front:
            print("   %-16s 前端 %s，IB 最早 %s" % (instrument_code, front_month, sample))
        print("解析失败 %d:" % len(failed))
        for instrument_code, message in failed[:40]:
            print("   %-16s %s" % (instrument_code, message))

    return 0


if __name__ == "__main__":
    sys.exit(main())
