#!/usr/bin/env python
"""
配置级回测：用生产管线跑一份配置，输出全历史 / 近 10 年 / 近 5 年指标。

指标口径（组合级、含成本、整手取整、延迟成交）：

* 累计收益：日收益复利；
* 年化收益 / 年化波动 / Sharpe：按 256 个交易日年化；
* 最大回撤：复利曲线相对历史高点的最深跌幅。

用法：

    python3 sysinit/henrik/backtest_config.py \
        --config private/futures_1m_v0.yaml --system v0 \
        --output docs/backtest_v0.csv
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

    return futures_system(data=data, config=config)


def daily_returns_for_system(system) -> pd.Series:
    """组合日收益（百分比，已含成本与整手取整）。"""
    portfolio = system.accounts.portfolio()
    daily = portfolio.percent.daily

    return daily.as_ts.dropna()


def net_gross_cost_returns(system) -> dict:
    """组合日收益（净/毛/成本，百分比）。"""
    portfolio = system.accounts.portfolio()

    return dict(
        net=portfolio.percent.daily.as_ts.dropna(),
        gross=portfolio.gross.percent.daily.as_ts.dropna(),
        costs=portfolio.costs.percent.daily.as_ts.dropna(),
    )


def average_rule_weights(system, start=None) -> pd.Series:
    """各规则的平均预测权重（先对品种、再对时间取平均）。"""
    weights = []
    for instrument_code in system.get_instrument_list():
        instrument_weights = system.combForecast.get_forecast_weights(instrument_code)
        if instrument_weights is None or instrument_weights.empty:
            continue
        if start is not None:
            instrument_weights = instrument_weights[
                instrument_weights.index >= start
            ]
        if not instrument_weights.empty:
            weights.append(instrument_weights.mean())

    if not weights:
        return pd.Series(dtype="float64")

    return pd.DataFrame(weights).mean().sort_values(ascending=False)


def instrument_attribution(system, start=None, top_n: int = 10) -> pd.DataFrame:
    """按品种拆解损益（百分比，正负为贡献方向）。"""
    rows = {}
    for instrument_code in system.get_instrument_list():
        try:
            curve = system.accounts.pandl_for_instrument(instrument_code)
        except Exception:
            continue
        returns = curve.percent.daily.as_ts.dropna()
        if start is not None:
            returns = returns[returns.index >= start]
        if returns.empty:
            continue
        compounded = float((1 + returns / 100.0).prod() - 1)
        rows[instrument_code] = dict(
            contribution=round(compounded, 4),
            annual=round(
                float((1 + compounded) ** (BUSINESS_DAYS_IN_YEAR / len(returns)) - 1), 4
            ),
            volatility=round(float(returns.std() * np.sqrt(BUSINESS_DAYS_IN_YEAR) / 100), 4),
        )

    table = pd.DataFrame(rows).T.sort_values("contribution")

    return table


def metrics(returns: pd.Series) -> dict:
    returns = returns.dropna() / 100.0
    if len(returns) < BUSINESS_DAYS_IN_YEAR // 2 or returns.std() == 0:
        return {}

    curve = (1 + returns).cumprod()
    years = len(returns) / BUSINESS_DAYS_IN_YEAR
    cumulative = float(curve.iloc[-1] - 1)
    annual_return = float((1 + cumulative) ** (1 / years) - 1)
    annual_volatility = float(returns.std() * np.sqrt(BUSINESS_DAYS_IN_YEAR))
    sharpe = float(returns.mean() / returns.std() * np.sqrt(BUSINESS_DAYS_IN_YEAR))
    max_drawdown = float((curve / curve.cummax() - 1).min())

    return dict(
        days=len(returns),
        start=str(returns.index[0].date()),
        end=str(returns.index[-1].date()),
        cumulative=round(cumulative, 4),
        annual_return=round(annual_return, 4),
        annual_volatility=round(annual_volatility, 4),
        sharpe=round(sharpe, 2),
        max_drawdown=round(max_drawdown, 4),
    )


def windows_for(index: pd.DatetimeIndex) -> list:
    end = index[-1]

    return [
        ("full", None, None),
        ("last10y", end - pd.DateOffset(years=10), None),
        ("last5y", end - pd.DateOffset(years=5), None),
    ]


def backtest(config_filename: str, system_name: str, output_filename: str) -> pd.DataFrame:
    system = build_system(config_filename, system_name)
    curves = net_gross_cost_returns(system)
    returns = curves["net"]

    rows = []
    for window_name, start, end in windows_for(returns.index):
        row = dict(window=window_name)
        for curve_name in ["net", "gross", "costs"]:
            window = curves[curve_name]
            if start is not None:
                window = window[window.index >= start]
            if end is not None:
                window = window[window.index < end]
            if curve_name == "costs":
                # 成本序列恒为正，直接年化求和，不套用收益指标
                row["costs_annual_pct"] = round(
                    float(window.mean() * BUSINESS_DAYS_IN_YEAR), 2
                )
                continue
            stats = metrics(window)
            if curve_name == "net":
                row.update(stats)
            else:
                row["gross_annual"] = stats.get("annual_return")
                row["gross_sharpe"] = stats.get("sharpe")
        rows.append(row)

    table = pd.DataFrame(rows).set_index("window")
    table.to_csv(output_filename)

    return table


def main():
    parser = argparse.ArgumentParser(description="配置级回测")
    parser.add_argument("--config", required=True)
    parser.add_argument(
        "--system",
        default="classic",
        choices=["classic", "v0"],
        help="classic：标准生产管线；v0：带 myFuturesRawData 的管线（skew 规则需要）",
    )
    parser.add_argument("--output", default="/private/tmp/backtest_config.csv")
    parser.add_argument(
        "--weights", action="store_true", help="同时输出各规则的平均预测权重"
    )
    parser.add_argument(
        "--attribution",
        action="store_true",
        help="同时输出近 5 年按品种的损益贡献（含实现波动）",
    )
    args = parser.parse_args()

    table = backtest(args.config, args.system, args.output)
    print(f"{args.config}（{args.system}）")
    print(table.to_markdown())
    if args.weights:
        system = build_system(args.config, args.system)
        end = daily_returns_for_system(system).index[-1]
        for label, start in [
            ("全历史", None),
            ("近5年", end - pd.DateOffset(years=5)),
        ]:
            weights = average_rule_weights(system, start=start)
            print(f"\n{label}平均预测权重（占比 %）：")
            print((weights * 100).round(1).to_string())
    if args.attribution:
        system = build_system(args.config, args.system)
        end = daily_returns_for_system(system).index[-1]
        table = instrument_attribution(system, start=end - pd.DateOffset(years=5))
        print("\n近 5 年品种损益归因（贡献为区间复利，按贡献升序）：")
        print(table.to_markdown())
        print(f"\n合计复利：{table.contribution.sum():.2%}，实现波动（等权）中位数：{table.volatility.median():.1%}")
    print(f"结果已写入 {args.output}")


if __name__ == "__main__":
    main()
