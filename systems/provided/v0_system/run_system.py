"""
v0 系统：标准生产管线 + rob_system 的 myFuturesRawData。

与 systems/provided/futures_chapter15/basesystem.py:futures_system 的唯一区别是
rawdata 阶段用 myFuturesRawData，以支持 skew 族规则（rawdata.get_demeanded_factor_value）。
其余阶段与当前生产一致（Account / Portfolios / PositionSizing / ForecastCombine /
ForecastScaleCap / Rules），保证与经典系统可直接对比。
"""

from syscore.constants import arg_not_supplied

from sysdata.config.configdata import Config
from sysdata.sim.csv_futures_sim_data import csvFuturesSimData

from systems.accounts.accounts_stage import Account
from systems.basesystem import System
from systems.forecast_combine import ForecastCombine
from systems.forecast_scale_cap import ForecastScaleCap
from systems.forecasting import Rules
from systems.portfolio import Portfolios
from systems.positionsizing import PositionSizing
from systems.provided.rob_system.rawdata import myFuturesRawData


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
            ForecastScaleCap(),
            rules,
        ],
        data,
        config,
    )

    return system
