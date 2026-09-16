from matplotlib.pyplot import title
import matplotlib.pyplot as plt
import nbformat
import datetime

import pandas as pd

from syscore.constants import arg_not_supplied
from syscore.dateutils import ROOT_BDAYS_INYEAR, BUSINESS_DAYS_IN_YEAR


def make_account_curve_plot(
    daily_pandl: pd.Series,
    start_of_title: str = "",
    start_date: datetime.datetime = arg_not_supplied,
    end_date: datetime.datetime = arg_not_supplied,
):
    curve_to_plot = daily_pandl.resample("1B").sum()
    if start_date is not arg_not_supplied:
        curve_to_plot = curve_to_plot[start_date:]
    if end_date is not arg_not_supplied:
        curve_to_plot = curve_to_plot[:end_date]

    # FIXME WOULD BE MUCH NICER IF THIS WAS AN ACCOUNT CURVE OBJECT
    avg_return = curve_to_plot.mean()
    std_return = curve_to_plot.std()
    ann_return = BUSINESS_DAYS_IN_YEAR * avg_return
    ann_std = ROOT_BDAYS_INYEAR * std_return
    ann_sr = ann_return / ann_std

    full_title = "%s ann. mean %.1f ann. std %1.f ann. SR %.2f" % (
        start_of_title,
        ann_return,
        ann_std,
        ann_sr,
    )
    curve_to_plot.cumsum().plot()
    title(full_title)


def make_account_curve_plot_from_df(
    pandl_df: pd.DataFrame,
    start_of_title: str = "",
    start_date: datetime.datetime = arg_not_supplied,
    end_date: datetime.datetime = arg_not_supplied,
    title_style: dict = None,
):
    curve_to_plot = pandl_df.resample("1B").sum()
    if start_date is not arg_not_supplied:
        curve_to_plot = curve_to_plot[start_date:]
    if end_date is not arg_not_supplied:
        curve_to_plot = curve_to_plot[:end_date]

    # FIXME WOULD BE MUCH NICER IF THIS WAS AN ACCOUNT CURVE OBJECT
    # AND WASN'T DIFFERENT FROM THE ABOVE

    avg_returns = curve_to_plot.mean()
    std_returns = curve_to_plot.std()
    ann_returns = BUSINESS_DAYS_IN_YEAR * avg_returns
    ann_std = ROOT_BDAYS_INYEAR * std_returns
    ann_sr = ann_returns / ann_std

    full_title = "%s \n ann. mean %s \n ann. std %s \n ann. SR %s" % (
        start_of_title,
        str(ann_returns.round(3).to_dict()),
        str(ann_std.round(3).to_dict()),
        str(ann_sr.round(2).to_dict()),
    )
    curve_to_plot.cumsum().plot()
    title(full_title, fontdict=title_style)


def nice_format_min_capital_table(min_capital_pd: pd.DataFrame) -> pd.DataFrame:
    min_capital_pd.point_size_base = min_capital_pd.point_size_base.round(1)
    min_capital_pd.price = min_capital_pd.price.round(3)
    min_capital_pd.annual_perc_stdev = min_capital_pd.annual_perc_stdev.round(1)
    min_capital_pd.risk_target = min_capital_pd.risk_target.round(3)
    min_capital_pd.minimum_capital_one_contract = (
        min_capital_pd.minimum_capital_one_contract.astype(int)
    )
    min_capital_pd.minimum_position_contracts = (
        min_capital_pd.minimum_position_contracts.astype(int)
    )
    min_capital_pd.instrument_weight = min_capital_pd.instrument_weight.round(2)
    min_capital_pd.IDM = min_capital_pd.IDM.round(2)
    min_capital_pd.minimum_capital = min_capital_pd.minimum_capital.astype(int)

    return min_capital_pd


def nice_format_roll_table(roll_table: pd.DataFrame) -> pd.DataFrame:
    roll_table.relative_volume_fwd = roll_table.relative_volume_fwd.astype(float)
    roll_table.relative_volume_fwd = roll_table.relative_volume_fwd.round(3)
    roll_table.contract_volume_fwd = roll_table.contract_volume_fwd.astype(int)

    return roll_table


def nice_format_slippage_table(slippage_table: pd.DataFrame) -> pd.DataFrame:
    slippage_table.Difference = slippage_table.Difference.round(1)
    slippage_table.bid_ask_trades = slippage_table.bid_ask_trades.round(4)
    slippage_table.total_trades = slippage_table.total_trades.round(4)
    slippage_table.bid_ask_sampled = slippage_table.bid_ask_sampled.round(4)
    slippage_table.weight_trades = slippage_table.weight_trades.round(2)
    slippage_table.weight_samples = slippage_table.weight_samples.round(2)
    slippage_table.weight_config = slippage_table.weight_config.round(2)
    slippage_table.estimate = slippage_table.estimate.round(4)
    slippage_table.Configured = slippage_table.Configured.round(4)

    return slippage_table


def nice_format_liquidity_table(liquidity_table: pd.DataFrame) -> pd.DataFrame:
    liquidity_table = liquidity_table.dropna()
    liquidity_table = liquidity_table.astype({"contracts": "int64"})
    liquidity_table = liquidity_table.round({"risk": 2})
    return liquidity_table


def nice_format_instrument_risk_table(
    instrument_risk_data: pd.DataFrame,
) -> pd.DataFrame:
    instrument_risk_data.daily_price_stdev = (
        instrument_risk_data.daily_price_stdev.round(3)
    )
    instrument_risk_data.annual_price_stdev = (
        instrument_risk_data.annual_price_stdev.round(3)
    )
    instrument_risk_data.price = instrument_risk_data.price.round(2)
    instrument_risk_data.daily_perc_stdev = instrument_risk_data.daily_perc_stdev.round(
        2
    )
    instrument_risk_data.annual_perc_stdev = (
        instrument_risk_data.annual_perc_stdev.round(1)
    )
    instrument_risk_data.point_size_base = instrument_risk_data.point_size_base.round(1)
    instrument_risk_data.contract_exposure = (
        instrument_risk_data.contract_exposure.astype(int)
    )
    instrument_risk_data.daily_risk_per_contract = (
        instrument_risk_data.daily_risk_per_contract.astype(int)
    )
    instrument_risk_data.annual_risk_per_contract = (
        instrument_risk_data.annual_risk_per_contract.astype(int)
    )
    instrument_risk_data.position = instrument_risk_data.position.astype(int)
    instrument_risk_data.capital = instrument_risk_data.capital.astype(int)
    instrument_risk_data.exposure_held_perc_capital = (
        instrument_risk_data.exposure_held_perc_capital.round(1)
    )
    instrument_risk_data.annual_risk_perc_capital = (
        instrument_risk_data.annual_risk_perc_capital.round(1)
    )

    return instrument_risk_data

def plot_total_assets(asset_series: pd.Series,
                      title: str = "Total Assets Over Time",
                      ma_days: int = 30,
                      currency: str = "HKD",
                      use_plotly: bool = False, 
                      start_date: datetime.datetime = arg_not_supplied,
                      end_date: datetime.datetime = arg_not_supplied):
    """
    资产总额可视化函数（静态或交互式）
    
    Parameters:
    - asset_series: pd.Series，index 为日期，值为资产总额
    - title: 图表标题
    - ma_days: 移动平均窗口天数
    - currency: 币种标注（如 "CNY", "USD"）
    - use_plotly: 是否使用 Plotly 交互图（默认 False）
    """
    if not isinstance(asset_series.index, pd.DatetimeIndex):
        raise ValueError("asset_series 的 index 必须为 DatetimeIndex")
    
    if start_date is not arg_not_supplied:
        asset_series = asset_series[start_date:]
    if end_date is not arg_not_supplied:
        asset_series = asset_series[:end_date]

    # 平滑趋势线
    ma_series = asset_series.rolling(window=ma_days).mean()

    if use_plotly:
        import plotly.graph_objects as go

        fig = go.Figure()
        fig.add_trace(go.Scatter(x=asset_series.index, y=asset_series,
                                 mode='lines', name='Total Assets',
                                 line=dict(color='blue')))
        fig.add_trace(go.Scatter(x=ma_series.index, y=ma_series,
                                 mode='lines', name=f'{ma_days}-day MA',
                                 line=dict(color='orange', dash='dash')))
        fig.update_layout(title=title,
                          xaxis_title="Date",
                          yaxis_title=f"Amount ({currency})",
                          template="plotly_white")
        fig.show()

    else:
        plt.style.use("seaborn-v0_8-whitegrid")
        fig, ax = plt.subplots(figsize=(14, 6))

        asset_series.plot(ax=ax, color='navy', linewidth=2, label='Total Assets')
        ma_series.plot(ax=ax, color='orange', linestyle='--', linewidth=1.5, label=f'{ma_days}-day MA')

        # 高点注释
        max_val = asset_series.max()
        max_date = asset_series.idxmax()
        ax.annotate(f"Peak: {max_val:,.0f} {currency}",
                    xy=(max_date, max_val),
                    xytext=(max_date, max_val * 1.05),
                    arrowprops=dict(arrowstyle='->', color='gray'),
                    fontsize=10)

        # 日期格式优化
       
        ax.set_title(title, fontsize=18, fontweight='bold')
        ax.set_xlabel("Date", fontsize=12)
        ax.set_ylabel(f"Amount ({currency})", fontsize=12)
        ax.legend()
        ax.grid(True, alpha=0.3)
        fig.autofmt_xdate()
        plt.tight_layout()
        plt.show()
