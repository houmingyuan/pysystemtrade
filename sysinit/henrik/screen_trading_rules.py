#!/usr/bin/env python
"""
单规则体检（rule screening）。

目的：在不动用完整回测系统的前提下，量化每条候选规则变体的「预测信息量」，
作为自建规则体系的筛选环节。做法与 Rob Carver《Systematic Trading》第 3/7 章
及附录 B/D 的规则评估口径一致：

1. 仓库内的规则函数已经把原始预测做波动率标准化；
2. 再把预测标定到平均绝对值 ≈ 10，标量只用窗口开始之前的数据估计（禁止时间机器）；
3. 单位风险持仓的日损益 = 前一日预测 × 当日价格变动 / 前一日价格波动；
   注意不能用 adjusted prices 的百分比收益：部分品种（GILT / OJ / ROBUSTA 等）
   的 adjusted price 会出现负值，百分比收益无意义，而本仓库的 adjusted price
   差分本身已代表滚动持仓的价格损益；
4. 规则在所有品种上等风险加权汇总，得到日损益序列；其 Sharpe 即规则的信息量。
   这不是完整策略收益：组合分散化、成本、整手取整都会再打折扣。

用法示例：

    python3 sysinit/henrik/screen_trading_rules.py \
        --config private/futures_1m_recommended.yaml \
        --output docs/rule_screen_latest.csv
"""

import argparse
from copy import copy

import numpy as np
import pandas as pd

from sysdata.config.configdata import Config
from systems.accounts.accounts_stage import Account
from systems.basesystem import System
from systems.forecast_combine import ForecastCombine
from systems.forecast_scale_cap import ForecastScaleCap
from systems.forecasting import Rules
from systems.portfolio import Portfolios
from systems.positionsizing import PositionSizing
from systems.rawdata import RawData
from sysproduction.data.sim_data import get_sim_data_object_for_production

BUSINESS_DAYS_IN_YEAR = 256
FORECAST_AVG_ABS = 10.0
FORECAST_CAP = 20.0
INCUMBENT_RULE = "ewmac16_64"
CORRELATION_CUTOFF = 0.95


def screening_rule_set() -> dict:
    """
    候选规则池：每个想法只放少量变体，变体之间只在交易速度上有差异（第 3 章）。
    函数路径与仓库既有实现一致，便于通过后再接回生产配置。
    """
    price_and_vol = ["rawdata.get_daily_prices", "rawdata.daily_returns_volatility"]
    trading_rules = {}

    for fast, slow in [(2, 8), (4, 16), (8, 32), (16, 64), (32, 128), (64, 256)]:
        trading_rules[f"ewmac{fast}_{slow}"] = dict(
            function="systems.provided.rules.ewmac.ewmac",
            data=price_and_vol,
            other_args=dict(Lfast=fast, Lslow=slow),
        )

    for lookback in [10, 20, 40, 80, 160, 320]:
        trading_rules[f"breakout{lookback}"] = dict(
            function="systems.provided.rules.breakout.breakout",
            data=["rawdata.get_daily_prices"],
            other_args=dict(lookback=lookback),
        )

    for fast in [16, 32, 64]:
        trading_rules[f"accel{fast}"] = dict(
            function="systems.provided.rules.accel.accel",
            data=price_and_vol,
            other_args=dict(Lfast=fast),
        )

    for fast in [4, 16]:
        trading_rules[f"mr_wings{fast}"] = dict(
            function="systems.provided.rules.mr_wings.mr_wings",
            data=price_and_vol,
            other_args=dict(Lfast=fast),
        )

    for smooth_days in [10, 30, 60, 125]:
        trading_rules[f"carry{smooth_days}"] = dict(
            function="systems.provided.rules.carry.carry",
            data=["rawdata.raw_carry"],
            other_args=dict(smooth_days=smooth_days),
        )

    return trading_rules


def rawdata_class_for(name: str):
    if name == "rob":
        from systems.provided.rob_system.rawdata import myFuturesRawData

        return myFuturesRawData

    return RawData


def build_system(config_filename: str, trading_rules: dict, rawdata_name: str = "standard"):
    data = get_sim_data_object_for_production()
    config = Config(config_filename)
    config = copy(config)
    config.trading_rules = trading_rules
    config.rule_variations = list(trading_rules.keys())

    system = System(
        [
            Account(),
            Portfolios(),
            PositionSizing(),
            rawdata_class_for(rawdata_name)(),
            ForecastCombine(),
            ForecastScaleCap(),
            Rules(),
        ],
        data,
        config,
    )

    return system, config


def rule_data_for_instruments(system, instrument_codes: list, rule_name: str) -> dict:
    """
    逐品种取规则原始预测与百分比收益。原始预测为波动率标准化的量（价格变化 / 价格波动），
    标定放在窗口内做，避免标量本身引入前视。
    """
    rule_data = {}
    for instrument_code in instrument_codes:
        try:
            raw_forecast = system.rules.get_raw_forecast(instrument_code, rule_name)
        except Exception:
            # 部分规则在扩展品种池上对个别品种无数据（例如资产类别内没有可比品种），
            # 这类品种在规则层面跳过，不影响其余品种的体检
            continue
        if isinstance(raw_forecast, pd.DataFrame):
            raw_forecast = raw_forecast.iloc[:, 0]
        raw_forecast = raw_forecast.dropna()
        if raw_forecast.empty:
            continue

        prices = system.rawdata.get_daily_prices(instrument_code)
        price_changes = prices.diff()
        price_volatility = system.rawdata.daily_returns_volatility(instrument_code)
        price_volatility = price_volatility.reindex(price_changes.index).ffill()
        rule_data[instrument_code] = dict(
            raw_forecast=raw_forecast,
            price_changes=price_changes,
            price_volatility=price_volatility,
        )

    return rule_data


def forecast_scalar(raw_forecast: pd.Series, up_to=None) -> float:
    """标量只用窗口开始之前的数据估计（第 3 章：禁止时间机器）。"""
    if up_to is not None:
        raw_forecast = raw_forecast[raw_forecast.index < up_to]
    average_abs = raw_forecast.abs().mean()
    if not np.isfinite(average_abs) or average_abs <= 0:
        return np.nan

    return FORECAST_AVG_ABS / average_abs


def pooled_pnl(rule_data: dict, start=None, end=None) -> pd.Series:
    """
    把同一规则在所有品种上的单位风险日损益等权平均（各品种风险预算相同）。

    预测在前一日收盘后已知，赚取次日收益，因此用 shift(1)。
    """
    all_pnl = {}
    for instrument_code, data in rule_data.items():
        raw_forecast = data["raw_forecast"]
        scalar = forecast_scalar(raw_forecast, up_to=start)
        if not np.isfinite(scalar):
            continue

        forecast = (raw_forecast * scalar).clip(-FORECAST_CAP, FORECAST_CAP)
        price_changes = data["price_changes"]
        price_volatility = data["price_volatility"]
        forecast = forecast.reindex(price_changes.index).ffill()

        # 单位风险持仓：predict_t-1 × (ΔP_t / σ_{t-1})
        risk_adjusted_return = price_changes / price_volatility.shift(1)
        pnl = forecast.shift(1) * risk_adjusted_return
        pnl = pnl.replace([np.inf, -np.inf], np.nan)

        if start is not None:
            pnl = pnl[pnl.index >= start]
        if end is not None:
            pnl = pnl[pnl.index < end]
        pnl = pnl.dropna()
        if not pnl.empty:
            all_pnl[instrument_code] = pnl

    if not all_pnl:
        return pd.Series(dtype="float64")

    return pd.DataFrame(all_pnl).mean(axis=1).dropna()


def sharpe_of(pnl: pd.Series) -> float:
    pnl = pnl.dropna()
    if len(pnl) < BUSINESS_DAYS_IN_YEAR // 2 or pnl.std() == 0:
        return np.nan

    return float(pnl.mean() / pnl.std() * np.sqrt(BUSINESS_DAYS_IN_YEAR))


def turnover_of(rule_data: dict) -> float:
    """每年「换手次数」估算：预测平均绝对变化 / 平均绝对预测，按半年往返折算。"""
    turnovers = []
    for data in rule_data.values():
        raw_forecast = data["raw_forecast"]
        average_abs = raw_forecast.abs().mean()
        if average_abs > 0:
            turnovers.append(raw_forecast.diff().abs().mean() / average_abs)

    if not turnovers:
        return np.nan

    return float(np.mean(turnovers) * BUSINESS_DAYS_IN_YEAR / 2.0)


def instrument_consistency(rule_data: dict, start=None) -> float:
    """品种层面的一致性：全历史 Sharpe 为正的品种比例。"""
    sharpes = [sharpe_of(pooled_pnl({code: data}, start=start)) for code, data in rule_data.items()]
    sharpes = [value for value in sharpes if np.isfinite(value)]
    if not sharpes:
        return np.nan

    return float(np.mean([value > 0 for value in sharpes]))


def windows_for(end_date: pd.Timestamp) -> list:
    def years_ago(years: int) -> pd.Timestamp:
        return end_date - pd.DateOffset(years=years)

    return [
        ("full", None, None),
        ("last10y", years_ago(10), None),
        ("last5y", years_ago(5), None),
        ("prev5y", years_ago(10), years_ago(5)),
    ]


def available_universe(
    system,
    min_years: float = 10.0,
    max_correlation: float = 0.98,
    max_stale_days: int = 60,
) -> list:
    """
    从价格库挑选可评估的扩展品种池：

    * 历史长度 ≥ min_years，且末端未过期（数据仍在推进）；
    * 按「同一条规则在不同品种上的收益相关性」剪枝，剔除与已保留品种相关 > max_correlation
      的重复市场（例如同一标的的 micro 与标准合约），避免同一风险被重复计数。
    """
    data = system.data
    end_date = pd.Timestamp.today().normalize()
    min_start_date = end_date - pd.DateOffset(years=min_years)

    candidates = []
    for instrument_code in data.get_instrument_list():
        try:
            prices = _adjusted_prices(data, instrument_code)
        except Exception:
            continue
        if prices is None or len(prices) < 200:
            continue
        if prices.index[0] > min_start_date:
            continue
        if (end_date - prices.index[-1]).days > max_stale_days:
            continue
        candidates.append(instrument_code)

    candidates = sorted(candidates, key=lambda code: _adjusted_prices(data, code).index[0])

    kept = []
    kept_returns = {}
    for instrument_code in candidates:
        prices = _adjusted_prices(data, instrument_code)
        volatility = system.rawdata.daily_returns_volatility(instrument_code)
        normalised = (prices.diff() / volatility.shift(1)).replace(
            [np.inf, -np.inf], np.nan
        )
        duplicated = False
        for kept_code in kept:
            other = kept_returns[kept_code]
            common = normalised.dropna().index.intersection(other.dropna().index)
            if len(common) < 500:
                continue
            correlation = normalised.reindex(common).corr(other.reindex(common))
            if np.isfinite(correlation) and abs(correlation) > max_correlation:
                duplicated = True
                break
        if duplicated:
            continue
        kept.append(instrument_code)
        kept_returns[instrument_code] = normalised

    return kept


def _adjusted_prices(data, instrument_code: str):
    return data.db_futures_adjusted_prices_data.get_adjusted_prices(instrument_code)


def screen(
    config_filename: str,
    output_filename: str,
    rule_names: list,
    universe: str = "config",
    max_correlation: float = 0.98,
    min_years: float = 10.0,
    rules_from_config: bool = False,
    rawdata_name: str = "standard",
) -> pd.DataFrame:
    if rules_from_config:
        candidate_rules = Config(config_filename).trading_rules
    else:
        candidate_rules = screening_rule_set()
    trading_rules = {
        key: value
        for key, value in candidate_rules.items()
        if not rule_names or key in rule_names
    }
    if not trading_rules:
        raise Exception(f"没有匹配的规则：{rule_names}")

    system, config = build_system(config_filename, trading_rules, rawdata_name=rawdata_name)
    if universe == "available":
        instrument_codes = available_universe(
            system, min_years=min_years, max_correlation=max_correlation
        )
        with open(f"{output_filename}.universe.txt", "w") as universe_file:
            universe_file.write("\n".join(instrument_codes))
    else:
        instrument_codes = list(config.instruments)
    print(f"品种池规模：{len(instrument_codes)}")
    end_date = pd.Timestamp.today().normalize()
    windows = windows_for(end_date)

    rows = []
    pooled_pnl_by_rule = {}
    for rule_name in trading_rules:
        rule_data = rule_data_for_instruments(system, instrument_codes, rule_name)
        if not rule_data:
            continue

        row = dict(
            rule=rule_name,
            turnover=round(turnover_of(rule_data), 1),
            instruments_positive=round(instrument_consistency(rule_data), 2),
        )
        for window_name, start, end in windows:
            pnl = pooled_pnl(rule_data, start=start, end=end)
            row[f"SR_{window_name}"] = round(sharpe_of(pnl), 2)
            if window_name == "full":
                pooled_pnl_by_rule[rule_name] = pnl
        rows.append(row)

    results = pd.DataFrame(rows).set_index("rule")

    if len(pooled_pnl_by_rule) > 1:
        pnl_frame = pd.DataFrame(pooled_pnl_by_rule)
        correlations = pnl_frame.corr()
        correlations.round(3).to_csv(f"{output_filename}.corr.csv")
        off_diagonal = correlations.where(
            ~np.eye(len(correlations), dtype=bool)
        ).abs()
        results["max_abs_corr"] = off_diagonal.max().round(2)
        results["most_correlated_with"] = off_diagonal.idxmax()
        if INCUMBENT_RULE in pnl_frame.columns:
            results["corr_with_incumbent"] = correlations[INCUMBENT_RULE].round(2)
    else:
        correlations = None

    results = results.sort_values("SR_full", ascending=False)
    results.to_csv(output_filename)

    if correlations is not None:
        selected = greedy_selection(results, correlations)
        with open(f"{output_filename}.selected.txt", "w") as selected_file:
            selected_file.write("\n".join(selected))
        print(f"按 |corr| <= {CORRELATION_CUTOFF} 贪心保留 {len(selected)} 条规则：")
        print("  " + ", ".join(selected))

    return results


def greedy_selection(
    results: pd.DataFrame, correlations: pd.DataFrame, threshold: float = CORRELATION_CUTOFF
) -> list:
    """
    按全历史 SR 从高到低遍历，若与已保留规则相关性都不超过阈值则保留。
    对应第 3 章「两个变体相关超过 95% 应删除一个」。
    """
    ordered = results["SR_full"].sort_values(ascending=False).index
    selected = []
    for rule_name in ordered:
        if all(abs(correlations.loc[rule_name, kept]) <= threshold for kept in selected):
            selected.append(rule_name)

    return selected


def main():
    parser = argparse.ArgumentParser(description="单规则体检（预测信息量筛选）")
    parser.add_argument(
        "--config",
        default="private/futures_1m_recommended.yaml",
        help="品种池与资本口径来自该配置",
    )
    parser.add_argument(
        "--output", default="/private/tmp/rule_screen_latest.csv", help="结果 CSV 路径"
    )
    parser.add_argument(
        "--rules", nargs="*", default=[], help="只筛这些规则名（默认全部候选）"
    )
    parser.add_argument(
        "--rules-source",
        default="screening",
        choices=["screening", "config"],
        help="screening：脚本内置候选池；config：用 --config 文件里的 trading_rules",
    )
    parser.add_argument(
        "--rawdata",
        default="standard",
        choices=["standard", "rob"],
        help="standard：基础 RawData；rob：rob_system 的 myFuturesRawData（skew 等因子规则需要）",
    )
    parser.add_argument(
        "--universe",
        default="config",
        choices=["config", "available"],
        help="config：用配置里的品种；available：价格库里历史足够的品种（自动去重）",
    )
    parser.add_argument(
        "--min-years", type=float, default=10.0, help="available 品种池要求的最短历史"
    )
    parser.add_argument(
        "--max-correlation",
        type=float,
        default=0.98,
        help="available 品种池的重复市场剪枝阈值",
    )
    args = parser.parse_args()

    results = screen(
        args.config,
        args.output,
        args.rules,
        universe=args.universe,
        max_correlation=args.max_correlation,
        min_years=args.min_years,
        rules_from_config=args.rules_source == "config",
        rawdata_name=args.rawdata,
    )
    print(results.to_markdown())
    print(f"\n结果已写入 {args.output}")


if __name__ == "__main__":
    main()
