#!/usr/bin/env python
"""
汇总当前交易品种规模与分类。

分层口径：

* 配置层：data/futures/csvconfig/instrumentconfig.csv 中的品种；
* IB 可解析：sysbrokers/IB/config/ib_config_futures.csv 中有映射的品种；
* 价格库有数据：adjusted prices 存在的品种；
* 历史 >= 10 年：价格库中历史长度达标（未做去重，去重后的评估品种池见
  docs/rule_screen_universe88.txt）；
* 生产在用：private_config.yaml 的 strategy_list 指向的配置里的品种。

用法：

    python3 sysinit/henrik/summarise_universe.py --output docs/universe_summary.csv
"""

import argparse

import pandas as pd
import yaml

from sysdata.config.production_config import get_production_config
from sysproduction.data.sim_data import get_sim_data_object_for_production

INSTRUMENT_CONFIG = "data/futures/csvconfig/instrumentconfig.csv"
IB_CONFIG = "sysbrokers/IB/config/ib_config_futures.csv"
MIN_HISTORY_YEARS = 10


def production_instruments() -> list:
    config = get_production_config()
    strategy_list = config.get_element_or_default("strategy_list", {})
    instruments = []
    for strategy_name in strategy_list:
        try:
            strategy_config = get_production_config().get_element_or_default(
                strategy_name, {}
            )
        except Exception:
            strategy_config = {}
        # 生产策略的品种来自其专用配置文件
        for candidate in [
            f"private/futures_{strategy_name}.yaml",
            "private/futures_available_small.yaml",
        ]:
            try:
                with open(candidate) as config_file:
                    loaded = yaml.safe_load(config_file)
                instruments.extend(loaded.get("instruments", []))
                break
            except FileNotFoundError:
                continue

    return sorted(set(instruments))


def price_store_history() -> pd.DataFrame:
    data = get_sim_data_object_for_production()
    rows = []
    for instrument_code in data.get_instrument_list():
        try:
            prices = data.db_futures_adjusted_prices_data.get_adjusted_prices(
                instrument_code
            )
        except Exception:
            continue
        if prices is None or len(prices) == 0:
            continue
        rows.append(
            dict(
                Instrument=instrument_code,
                start=prices.index[0],
                end=prices.index[-1],
                years=round((prices.index[-1] - prices.index[0]).days / 365.25, 1),
            )
        )

    return pd.DataFrame(rows).set_index("Instrument")


def summarise(output_filename: str):
    metadata = pd.read_csv(INSTRUMENT_CONFIG).set_index("Instrument")
    ib_mapped = set(pd.read_csv(IB_CONFIG)["Instrument"])
    history = price_store_history()
    production = production_instruments()

    table = pd.DataFrame(index=metadata.index)
    table["asset_class"] = metadata["AssetClass"]
    table["region"] = metadata["Region"]
    table["currency"] = metadata["Currency"]
    table["in_ib"] = table.index.isin(ib_mapped)
    table["in_price_store"] = table.index.isin(history.index)
    table["years"] = history["years"].reindex(table.index)
    table["history_10y"] = table["years"] >= MIN_HISTORY_YEARS
    table["in_production"] = table.index.isin(production)

    by_class = (
        table.groupby("asset_class")
        .agg(
            配置=("in_ib", "size"),
            IB可解析=("in_ib", "sum"),
            价格库有数据=("in_price_store", "sum"),
            历史10年以上=("history_10y", "sum"),
            生产在用=("in_production", "sum"),
        )
        .sort_values("价格库有数据", ascending=False)
    )
    by_class.loc["合计"] = by_class.sum()
    by_class = by_class.astype(int)

    by_region = (
        table[table["in_price_store"]]
        .groupby("region")
        .agg(价格库有数据=("in_price_store", "sum"), 历史10年以上=("history_10y", "sum"))
        .sort_values("价格库有数据", ascending=False)
    )

    table.to_csv(output_filename)

    return by_class, by_region, table


def main():
    parser = argparse.ArgumentParser(description="汇总交易品种规模与分类")
    parser.add_argument("--output", default="docs/universe_summary.csv")
    args = parser.parse_args()

    by_class, by_region, table = summarise(args.output)
    print("按资产类别：")
    print(by_class.to_markdown())
    print("\n按地区（仅价格库有数据的品种）：")
    print(by_region.to_markdown())
    print(f"\n品种明细已写入 {args.output}")


if __name__ == "__main__":
    main()
