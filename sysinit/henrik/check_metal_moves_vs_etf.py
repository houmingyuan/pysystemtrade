"""
FIR-127 第 B 步：用 ETF 日线核对 SILVER / GOLD 期货的大跳是不是真实行情（只读，不写价格库）。

同时从本机 IB Gateway 取：
  * ETF 日线：SLV（白银）、GLD / IAU（黄金）
  * 出现尖峰的期货合约日线：SILVER#20260900、GOLD#20261000、GOLD#20261200
ETF 与期货跟踪同一标的，正常情况日涨跌应高度一致；若期货出现 10%+ 而 ETF 只有零点几个百分点，
说明是数据问题而不是行情。

用法：
    python sysinit/henrik/check_metal_moves_vs_etf.py
    python sysinit/henrik/check_metal_moves_vs_etf.py --duration "2 Y"
"""

import argparse
import sys

import pandas as pd
from ib_async import IB, Stock, util

from syscore.dateutils import DAILY_PRICE_FREQ
from sysdata.data_blob import dataBlob
from sysobjects.contracts import futuresContract
from sysproduction.data.broker import dataBroker

ETF_SYMBOLS = ["SLV", "GLD", "IAU"]
FUTURES_TO_CHECK = [("SILVER", "20260900"), ("GOLD", "20261000"), ("GOLD", "20261200")]
SPIKE_DATE = pd.Timestamp("2026-01-30")
OUTPUT_CSV = "/tmp/fir127_metal_check.csv"


def daily_returns_from_bars(bars) -> pd.Series:
    frame = util.df(bars)
    if frame is None or len(frame) == 0:
        return pd.Series(dtype=float)
    frame["date"] = pd.to_datetime(frame["date"]).dt.normalize()
    frame = frame[["date", "close"]].drop_duplicates(subset="date", keep="last")
    frame = frame.set_index("date").sort_index()
    return frame["close"].pct_change().dropna() * 100.0


def fetch_etf_returns(ib, symbol, duration) -> pd.Series:
    bars = ib.reqHistoricalData(
        Stock(symbol, "SMART", "USD"),
        endDateTime="",
        durationStr=duration,
        barSizeSetting="1 day",
        whatToShow="TRADES",
        useRTH=True,
        formatDate=2,
    )
    return daily_returns_from_bars(bars)


def fetch_futures_returns(data, instrument_code, contract_date_str) -> pd.Series:
    """期货日收益：走仓库自己的 broker 层（与每日更新同一条取数路径）。"""
    contract_object = futuresContract(instrument_code, contract_date_str)
    raw = dataBroker(data).get_prices_at_frequency_for_contract_object(
        contract_object=contract_object, frequency=DAILY_PRICE_FREQ
    )
    frame = pd.DataFrame(raw)
    if len(frame) == 0:
        return pd.Series(dtype=float)
    frame = frame[~frame.index.duplicated(keep="last")].sort_index()
    return frame["FINAL"].astype(float).pct_change().dropna() * 100.0


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="用 ETF 核对金属期货尖峰是否真实")
    parser.add_argument("--duration", default="1 Y")
    parser.add_argument("--port", type=int, default=4001)
    parser.add_argument("--client-id", type=int, default=991)
    args = parser.parse_args(argv)

    columns = {}
    with dataBlob(log_name="Metal-Spike-Vs-ETF") as data:
        ib = IB()
        ib.connect("127.0.0.1", args.port, clientId=args.client_id, timeout=20)
        print("已连接 IB 端口 %s（clientId=%s）" % (args.port, args.client_id), flush=True)

        for symbol in ETF_SYMBOLS:
            try:
                series = fetch_etf_returns(ib, symbol, args.duration)
                columns["ETF:" + symbol] = series
                print("  ETF %s: %d 条日收益" % (symbol, len(series)), flush=True)
            except Exception as error:
                print("  ETF %s 取数失败: %s: %s" % (symbol, type(error).__name__, str(error)[:80]))

        for instrument_code, contract_date_str in FUTURES_TO_CHECK:
            label = "FUT:%s#%s" % (instrument_code, contract_date_str)
            try:
                series = fetch_futures_returns(
                    data, instrument_code, contract_date_str
                )
                columns[label] = series
                print("  %s: %d 条日收益" % (label, len(series)), flush=True)
            except Exception as error:
                print("  %s 取数失败: %s: %s" % (label, type(error).__name__, str(error)[:80]))

        ib.disconnect()

    if not columns:
        print("没有任何序列可用")
        return 1

    table = pd.DataFrame(columns).sort_index()
    table.to_csv(OUTPUT_CSV)
    print("\n对齐后的日收益写入 %s（%d 个交易日）" % (OUTPUT_CSV, len(table)))

    print("\n各序列单日最大绝对涨跌（前 5）：")
    for name in table.columns:
        series = table[name].dropna()
        if len(series) == 0:
            continue
        top = series.abs().sort_values(ascending=False).head(5)
        moves = ", ".join("%s:%+.2f%%" % (date.date(), series[date]) for date in top.index)
        print("  %-24s 最大 %.2f%%   前五: %s" % (name, top.iloc[0], moves))

    print("\n尖峰日对照（%s，期货 vs ETF 同日涨跌）：" % SPIKE_DATE.date())
    if SPIKE_DATE in table.index:
        row = table.loc[SPIKE_DATE]
        for name in table.columns:
            if pd.isna(row[name]):
                continue
            print("  %-24s %+.2f%%" % (name, row[name]))
    else:
        print("  该日期没有数据")

    return 0


if __name__ == "__main__":
    sys.exit(main())
