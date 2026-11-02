"""
v0 系统：标准生产管线 + rob_system 的 myFuturesRawData。

与 systems/provided/futures_chapter15/basesystem.py:futures_system 的唯一区别是
rawdata 阶段用 myFuturesRawData，以支持 skew 族规则（rawdata.get_demeanded_factor_value）。
其余阶段与当前生产一致（Account / Portfolios / PositionSizing / ForecastCombine /
ForecastScaleCap / Rules），保证与经典系统可直接对比。

预测缩放用 volAttenForecastScaleCap（Carver 的波动率衰减）：只对配置 use_attenuation
里列出的规则生效，没有该配置时与 ForecastScaleCap 完全相同。

futures_system_dynamic：同一规则链路，仓位阶段换成动态优化，用于小资本。
"""

from syscore.constants import arg_not_supplied

from sysdata.config.configdata import Config
from sysdata.sim.csv_futures_sim_data import csvFuturesSimData

from systems.accounts.accounts_stage import Account
from systems.basesystem import System
from systems.forecast_combine import ForecastCombine
from systems.forecasting import Rules
from systems.portfolio import Portfolios
from systems.positionsizing import PositionSizing
from systems.provided.attenuate_vol.vol_attenuation_forecast_scale_cap import (
    volAttenForecastScaleCap,
)
from systems.provided.dynamic_small_system_optimise.accounts_stage import (
    accountForOptimisedStage,
)
from systems.provided.dynamic_small_system_optimise.optimised_positions_stage import (
    optimisedPositions,
)
from systems.provided.rob_system.rawdata import myFuturesRawData
from systems.risk import Risk


def futures_system(
    data=arg_not_supplied,
    config=arg_not_supplied,
    trading_rules=arg_not_supplied,
):
    """

    :param data: 数据对象，默认 csvFuturesSimData
    :param config: Config 对象或配置文件名
    :param trading_rules: 规则集合
    """
    if data is arg_not_supplied:
        data = csvFuturesSimData()

    if config is arg_not_supplied:
        config = Config("private.futures_1m_v0.yaml")

    rules = Rules(trading_rules)

    system = System(
        [
            Account(),
            Portfolios(),
            PositionSizing(),
            myFuturesRawData(),
            ForecastCombine(),
            volAttenForecastScaleCap(),
            rules,
        ],
        data,
        config,
    )

    return system


def futures_system_dynamic(
    data=arg_not_supplied,
    config=arg_not_supplied,
    trading_rules=arg_not_supplied,
):
    """
    v0 规则链路 + 动态优化（Carver《Advanced Futures Trading Strategies》第 25 章）。

    小资本下大部分品种的最优仓位不足 1 手，直接取整会让多数品种长期为 0 手。
    动态优化每天在全部品种里求最接近最优仓位的整数组合；组合盈亏用
    system.accounts.optimised_portfolio()。参数见 defaults.yaml 的 small_system。
    """
    if data is arg_not_supplied:
        data = csvFuturesSimData()

    if config is arg_not_supplied:
        config = Config("private.futures_1m_v8c.yaml")

    rules = Rules(trading_rules)

    system = System(
        [
            Risk(),
            accountForOptimisedStage(),
            optimisedPositions(),
            Portfolios(),
            PositionSizing(),
            myFuturesRawData(),
            ForecastCombine(),
            volAttenForecastScaleCap(),
            rules,
        ],
        data,
        config,
    )

    return system
