#!/usr/bin/env python
"""
交易成本分析（第 12 章 Speed and Size 口径）。

用框架自带的标准化成本把「成本」折算成 SR 单位（与资本规模无关的口径）：

* `get_SR_cost_per_trade_for_instrument`：单品种每次往返的标准化成本；
* `get_SR_holding_cost_only`：持仓维持成本（换月/展期带来的年化成本）；
* `get_SR_cost_for_instrument_forecast`：品种 × 规则的年化总成本（交易 + 持仓）。

用法：

    python3 sysinit/henrik/cost_analysis.py \
        --config private/futures_1m_v1.yaml --system v0 \
        --output docs/cost_analysis_v1.csv
"""

import argparse

import pandas as pd

from sysdata.config.configdata import Config
from sysproduction.data.sim_data import get_sim_data_object_for_production

CONTRACT_PAIRS = [
    ("SP500", "SP500_micro"),
    ("NASDAQ", "NASDAQ_micro"),
    ("GOLD", "GOLD_micro"),
    ("CRUDE_W", "CRUDE_W_micro"),
    ("CORN", "CORN_mini"),
]


def build_system(config_filename: str, system_name: str):
    data = get_sim_data_object_for_production()
    config = Config(config_filename)

    if system_name == "v0":
        from systems.provided.v0_system.run_system import futures_system
    else:
        from systems.provided.futures_chapter15.basesystem import futures_system

    return futures_system(data=data, config=config), config


def cost_table(system, config) -> pd.DataFrame:
    rules = list(config.rule_variations)
    rows = []
    for instrument_code in system.get_instrument_list():
        row = dict(
            instrument_code=instrument_code,
            per_trade=round(
                system.accounts.get_SR_cost_per_trade_for_instrument(instrument_code), 4
            ),
            holding=round(system.accounts.get_SR_holding_cost_only(instrument_code), 4),
        )
        for rule in rules:
            try:
                row[rule] = round(
                    system.accounts.get_SR_cost_for_instrument_forecast(
                        instrument_code, rule
                    ),
                    4,
                )
            except Exception:
                row[rule] = None
        rows.append(row)

    return pd.DataFrame(rows).set_index("instrument_code")


def contract_size_comparison(system) -> pd.DataFrame:
    """对比同一标的的标准合约与 micro/mini 合约的标准化成本。"""
    rows = []
    for full_code, micro_code in CONTRACT_PAIRS:
        row = dict(pair=f"{full_code} vs {micro_code}")
        for label, code in [("full", full_code), ("micro", micro_code)]:
            try:
                row[f"{label}_per_trade"] = round(
                    system.accounts.get_SR_cost_per_trade_for_instrument(code), 4
                )
                row[f"{label}_holding"] = round(
                    system.accounts.get_SR_holding_cost_only(code), 4
                )
            except Exception:
                row[f"{label}_per_trade"] = None
                row[f"{label}_holding"] = None
        if row.get("full_per_trade") and row.get("micro_per_trade"):
            row["micro_x_full"] = round(
                row["micro_per_trade"] / row["full_per_trade"], 2
            )
        rows.append(row)

    return pd.DataFrame(rows).set_index("pair")


def main():
    parser = argparse.ArgumentParser(description="交易成本分析（SR 单位）")
    parser.add_argument("--config", default="private/futures_1m_v1.yaml")
    parser.add_argument("--system", default="v0", choices=["classic", "v0"])
    parser.add_argument("--output", default="/private/tmp/cost_analysis.csv")
    args = parser.parse_args()

    system, config = build_system(args.config, args.system)
    table = cost_table(system, config)
    table.to_csv(args.output)

    rule_columns = list(config.rule_variations)
    print("各规则的年化成本（SR 单位，品种均值）：")
    print(table[rule_columns].mean().round(4).sort_values(ascending=False).to_string())
    print(
        f"\n组合层年化成本（SR 单位，等权品种均值）："
        f"{table[rule_columns].stack().mean():.4f}"
    )
    print("\n每次往返标准化成本最高的 10 个品种（SR 单位）：")
    print(table[["per_trade", "holding"]].sort_values("per_trade", ascending=False).head(10).to_string())

    print("\n标准合约 vs micro/mini（每次往返 SR 成本）：")
    print(contract_size_comparison(system).to_string())
    print(f"\n结果已写入 {args.output}")


if __name__ == "__main__":
    main()
