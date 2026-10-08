#!/usr/bin/env python
"""
业绩归因：按规则、按资产类别拆解指定窗口的损益，并给出滚动窗口分布。

用途：回答「为什么最近这段是亏损」——先分清多少来自成本、多少来自哪条规则/哪类资产，
再用历史滚动窗口分布判断这件事有多常见。

用法：

    python3 sysinit/henrik/attribute_performance.py \
        --config private/futures_1m_v3.yaml --system v0 --years 5 \
        --output docs/attribution_v3_last5y.csv
"""

import argparse

import numpy as np
import pandas as pd

from sysdata.config.configdata import Config
from sysproduction.data.sim_data import get_sim_data_object_for_production

BUSINESS_DAYS_IN_YEAR = 256


def build_system(config_filename: str, system_name: str):
    data = get_sim_data_object_for_production()
    config = Config(config_filename)

    if system_name == "v0":
        from systems.provided.v0_system.run_system import futures_system
    else:
        from systems.provided.futures_chapter15.basesystem import futures_system

    return futures_system(data=data, config=config), config


def asset_class_for(metadata: pd.DataFrame, instrument_code: str) -> str:
    try:
        return metadata.loc[instrument_code, "AssetClass"]
    except KeyError:
        return "Unknown"


def window_metrics(returns_percent: pd.Series) -> dict:
    returns = returns_percent.dropna() / 100.0
    if len(returns) < 20:
        return dict(cumulative=np.nan, sharpe=np.nan, volatility=np.nan)

    cumulative = float((1 + returns).prod() - 1)
    volatility = float(returns.std() * np.sqrt(BUSINESS_DAYS_IN_YEAR))
    sharpe = (
        float(returns.mean() / returns.std() * np.sqrt(BUSINESS_DAYS_IN_YEAR))
        if returns.std() > 0
        else np.nan
    )

    return dict(
        cumulative=round(cumulative, 4),
        sharpe=round(sharpe, 2),
        volatility=round(volatility, 4),
    )


def rolling_window_distribution(daily: pd.Series, years: int = 5) -> dict:
    """历史滚动窗口（复利）分布，用来判断当前结果在历史上的分位。"""
    window = int(years * BUSINESS_DAYS_IN_YEAR)
    log_returns = np.log1p(daily.dropna() / 100.0)
    rolling = np.exp(log_returns.rolling(window).sum()) - 1
    rolling = rolling.dropna()

    current = rolling.iloc[-1]
    percentile = float((rolling <= current).mean())

    return dict(
        windows=len(rolling),
        share_negative=round(float((rolling < 0).mean()), 4),
        worst=round(float(rolling.min()), 4),
        p10=round(float(rolling.quantile(0.10)), 4),
        median=round(float(rolling.median()), 4),
        p90=round(float(rolling.quantile(0.90)), 4),
        best=round(float(rolling.max()), 4),
        current=round(float(current), 4),
        current_percentile=round(percentile, 4),
    )


def main():
    parser = argparse.ArgumentParser(description="业绩归因")
    parser.add_argument("--config", default="private/futures_1m_v3.yaml")
    parser.add_argument("--system", default="v0", choices=["classic", "v0"])
    parser.add_argument("--years", type=float, default=5.0)
    parser.add_argument("--output", default="/private/tmp/attribution.csv")
    args = parser.parse_args()

    system, config = build_system(args.config, args.system)
    portfolio = system.accounts.portfolio()
    net = portfolio.percent.daily.as_ts.dropna()
    gross = portfolio.gross.percent.daily.as_ts.dropna()
    costs = portfolio.costs.percent.daily.as_ts.dropna()

    end = net.index[-1]
    start = end - pd.DateOffset(years=args.years)

    def cut(series):
        return series[series.index >= start]

    print(f"窗口：{start.date()} ~ {end.date()}")
    net_metrics = window_metrics(cut(net))
    gross_metrics = window_metrics(cut(gross))
    print(
        f"合计：净 {net_metrics['cumulative']:.2%}（SR {net_metrics['sharpe']}）、"
        f"毛 {gross_metrics['cumulative']:.2%}（SR {gross_metrics['sharpe']}）、"
        f"成本 {cut(costs).mean() * BUSINESS_DAYS_IN_YEAR:.2f}%/年"
    )

    # 规则层归因
    rules = list(config.rule_variations)
    by_rule = {}
    instrument_codes = system.get_instrument_list()
    for rule in rules:
        series = None
        for instrument_code in instrument_codes:
            curve = system.accounts.pandl_for_instrument_forecast_weighted(
                instrument_code, rule
            )
            instrument_series = curve.percent.daily.as_ts
            series = (
                instrument_series
                if series is None
                else series.add(instrument_series, fill_value=0)
            )
        by_rule[rule] = window_metrics(cut(series))
    rule_table = pd.DataFrame(by_rule).T.sort_values("cumulative")
    print("\n按规则（窗口内复利）：")
    print(rule_table.to_string())

    # 品种 / 资产类别归因
    metadata = pd.read_csv("data/futures/csvconfig/instrumentconfig.csv").set_index(
        "Instrument"
    )
    by_instrument = {}
    for instrument_code in system.get_instrument_list():
        curve = system.accounts.pandl_for_instrument(instrument_code)
        by_instrument[instrument_code] = window_metrics(cut(curve.percent.daily.as_ts.dropna()))
    instrument_table = pd.DataFrame(by_instrument).T
    instrument_table["asset_class"] = [
        asset_class_for(metadata, code) for code in instrument_table.index
    ]
    by_asset_class = (
        instrument_table.groupby("asset_class")
        .agg(
            cumulative=("cumulative", "sum"),
            sharpe=("sharpe", "mean"),
            instruments=("cumulative", "size"),
        )
        .sort_values("cumulative")
    )
    print("\n按资产类别（窗口内复利求和）：")
    print(by_asset_class.round(4).to_string())

    print(f"\n滚动 {args.years:g} 年窗口分布（全历史）：")
    print(rolling_window_distribution(net, args.years))

    instrument_table.to_csv(args.output)
    print(f"\n品种明细已写入 {args.output}")


if __name__ == "__main__":
    main()
