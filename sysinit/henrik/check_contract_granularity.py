#!/usr/bin/env python
"""
最小合约块检查（第 12 章 Speed and Size）。

判断在给定资本与品种数量下，每个品种在「最大风险仓位」（forecast = +20）
能否持有至少 4 张合约。粒度不足会让实盘仓位相对目标系统性偏小，
表现为实现波动低于目标（FIR-104、FIR-187 都出现过）。

口径：

    单品种年度现金波动预算 = 资本 × 目标波动 × IDM / 品种数
    每张合约年度现金波动   = 日价格波动(价格点) × Pointsize × 16
    max 仓位(张)           = 单品种年度现金波动预算 × (20/10) / 每张合约年度现金波动

未做货币换算（非 USD 报价合约按合约货币计算），用于筛选而非下单。

用法：

    python3 sysinit/henrik/check_contract_granularity.py \
        --universe-file /private/tmp/rule_screen_universe.csv.universe.txt \
        --capital 1000000 --instruments-count 88
"""

import argparse

import numpy as np
import pandas as pd

from sysdata.config.production_config import get_production_config
from sysproduction.data.sim_data import get_sim_data_object_for_production
from sysquant.estimators.vol import robust_vol_calc

INSTRUMENT_CONFIG = "data/futures/csvconfig/instrumentconfig.csv"
BUSINESS_DAYS_IN_YEAR = 256
DEFAULT_IDM = 1.5
FORECAST_CAP = 20.0
FORECAST_AVG_ABS = 10.0


def instrument_metadata() -> pd.DataFrame:
    table = pd.read_csv(INSTRUMENT_CONFIG)

    return table.set_index("Instrument")


def daily_price_volatility(adjusted_prices: pd.Series, config) -> float:
    volatility_config = config.get_element_or_default("volatility_calculation", {})
    volatility = robust_vol_calc(adjusted_prices.diff(), **volatility_config)

    return float(volatility.dropna().iloc[-1])


def max_position_in_contracts(
    price_volatility: float,
    pointsize: float,
    capital: float,
    percentage_vol_target: float,
    instrument_count: int,
    idm: float = DEFAULT_IDM,
) -> float:
    annual_cash_vol_per_contract = price_volatility * pointsize * np.sqrt(
        BUSINESS_DAYS_IN_YEAR
    )
    if annual_cash_vol_per_contract <= 0:
        return np.nan

    instrument_cash_vol_budget = (
        capital * percentage_vol_target / 100.0 * idm / instrument_count
    )
    max_forecast_multiplier = FORECAST_CAP / FORECAST_AVG_ABS

    return (
        instrument_cash_vol_budget * max_forecast_multiplier
        / annual_cash_vol_per_contract
    )


def run(
    universe: list,
    capitals: list,
    percentage_vol_target: float,
    instrument_count: int = None,
) -> pd.DataFrame:
    data = get_sim_data_object_for_production()
    config = get_production_config()
    metadata = instrument_metadata()

    if instrument_count is None:
        instrument_count = len(universe)

    rows = []
    for instrument_code in universe:
        if instrument_code not in metadata.index:
            continue
        try:
            prices = data.db_futures_adjusted_prices_data.get_adjusted_prices(
                instrument_code
            )
        except Exception:
            continue

        price_volatility = daily_price_volatility(prices, config)
        pointsize = float(metadata.loc[instrument_code, "Pointsize"])
        row = dict(
            instrument_code=instrument_code,
            asset_class=metadata.loc[instrument_code, "AssetClass"],
            last_price=float(prices.dropna().iloc[-1]),
            price_volatility=price_volatility,
            pointsize=pointsize,
        )
        for capital in capitals:
            row[f"maxpos_{instrument_count}_cap{int(capital / 1000)}k"] = (
                max_position_in_contracts(
                price_volatility,
                pointsize,
                capital,
                percentage_vol_target,
                instrument_count=instrument_count,
                )
            )
        rows.append(row)

    table = pd.DataFrame(rows).set_index("instrument_code")
    for capital in capitals:
        column = f"maxpos_{instrument_count}_cap{int(capital / 1000)}k"
        table[f"passes_4_contracts_cap{int(capital / 1000)}k"] = table[column] >= 4
        table[f"passes_2_contracts_cap{int(capital / 1000)}k"] = table[column] >= 2

    return table


def main():
    parser = argparse.ArgumentParser(description="最小合约块检查")
    parser.add_argument(
        "--universe-file",
        default="/private/tmp/rule_screen_universe.csv.universe.txt",
        help="每行一个品种代码",
    )
    parser.add_argument(
        "--capital",
        type=float,
        nargs="+",
        default=[1_000_000],
        help="可给多个资本规模，一次性对比",
    )
    parser.add_argument(
        "--instruments-count",
        type=int,
        default=None,
        help="风险预算的分母（默认取品种池规模）",
    )
    parser.add_argument("--percentage-vol-target", type=float, default=15.0)
    parser.add_argument("--output", default="/private/tmp/contract_granularity.csv")
    args = parser.parse_args()

    universe = [
        line.strip()
        for line in open(args.universe_file).read().splitlines()
        if line.strip()
    ]
    table = run(
        universe,
        args.capital,
        args.percentage_vol_target,
        instrument_count=args.instruments_count,
    )
    table.to_csv(args.output)

    instrument_count = args.instruments_count or len(table)
    print(f"品种数 {instrument_count}（池内 {len(table)}），目标波动 {args.percentage_vol_target}%，IDM {DEFAULT_IDM}，forecast +{FORECAST_CAP:.0f}")
    for capital in args.capital:
        suffix = f"cap{int(capital / 1000)}k"
        column = f"maxpos_{instrument_count}_{suffix}"
        print(
            f"资本 {capital:,.0f}：≥2 张 {int((table[column] >= 2).sum())}/{len(table)}，"
            f"≥4 张 {int((table[column] >= 4).sum())}/{len(table)}，"
            f"仓位中位数 {table[column].median():.2f} 张"
        )

    print(f"结果已写入 {args.output}")


if __name__ == "__main__":
    main()
