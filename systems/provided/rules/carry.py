import pandas as pd


def carry(raw_carry, smooth_days=90):
    """
    Calculate carry forecast, given that there exists a raw_carry() in rawdata

    Assumes that everything is daily data

    :param raw_carry: The annualised sharpe ratio of rolldown
    :type raw_carry: pd.DataFrame (assumed Tx1)

    >>> from systems.tests.testdata import get_test_object_futures
    >>> from systems.basesystem import System
    >>> (rawdata, data, config)=get_test_object_futures()
    >>> system=System( [rawdata], data, config)
    >>>
    >>> carry(rawdata.raw_carry("EDOLLAR")).tail(2)
    2015-12-10    0.411686
    2015-12-11    0.411686
    Freq: B, dtype: float64
    """

    smooth_carry = raw_carry.ewm(smooth_days).mean()

    return smooth_carry


def seasonally_adjusted_carry(raw_carry, smooth_days=90, min_years=3):
    """
    Seasonally adjusted carry (Carver, Advanced Futures Trading Strategies)

    Carry in ags and energies swings with the month being held. The seasonal component
    for each calendar month is the average, over earlier years only, of that month's
    carry minus the average carry of the same year, so there is no look-ahead.
    No adjustment is made for a month until it has min_years of history.

    :param raw_carry: The annualised sharpe ratio of rolldown
    :type raw_carry: pd.Series
    :param smooth_days: smoothing, as for carry()
    :param min_years: years of history needed before adjusting a month
    :return: forecast pd.Series
    """

    carry_values = raw_carry.dropna()
    years = carry_values.index.year
    months = carry_values.index.month

    deviation = carry_values - carry_values.groupby(years).transform("mean")
    monthly_deviation = deviation.groupby([years, months]).mean().unstack()

    # shift(1): each year only sees the years before it
    seasonal_by_year_month = (
        monthly_deviation.shift(1).expanding(min_periods=min_years).mean().stack()
    )
    seasonal = seasonal_by_year_month.reindex(
        pd.MultiIndex.from_arrays([years, months])
    ).fillna(0.0)

    adjusted_carry = carry_values - seasonal.values
    smooth_carry = adjusted_carry.reindex(raw_carry.index).ewm(smooth_days).mean()

    return smooth_carry


def relative_carry(smoothed_carry_this_instrument, median_carry_for_asset_class):
    """
    Relative carry rule
    Suggested inputs: rawdata.smoothed_carry, rawdata.median_carry_for_asset_class

    :param smoothed_carry_this_instrument: pd.Series
    :param median_carry_for_asset_class: pd.Series aligned to smoothed_carry_this_instrument
    :return: forecast pd.Series
    """

    # should already be aligned
    relative_carry_forecast = (
        smoothed_carry_this_instrument - median_carry_for_asset_class
    )

    return relative_carry_forecast
