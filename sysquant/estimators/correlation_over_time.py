import pandas as pd
import numpy as np
from syscore.interactive.progress_bar import progressBar
from sysquant.estimators.correlation_estimator import correlationEstimator

from sysquant.fitting_dates import generate_fitting_dates, listOfFittingDates
from sysquant.estimators.correlations import CorrelationList, correlationEstimate


def correlation_over_time_for_returns(
    returns_for_correlation: pd.DataFrame,
    frequency="W",
    forward_fill_price_index=True,
    **kwargs,
) -> CorrelationList:
    if returns_for_correlation.shape[1] == 0:
        # Nothing to correlate (eg no instruments with positions yet). Return
        # an empty correlation list instead of trying to resample an index that
        # is not a datetime index (which happens for an empty frame).
        return empty_correlation_list()

    index_prices_for_correlation = returns_for_correlation.cumsum()
    if forward_fill_price_index:
        index_prices_for_correlation = index_prices_for_correlation.ffill()

    index_prices_for_correlation = index_prices_for_correlation.resample(
        frequency
    ).last()
    returns_for_correlation = index_prices_for_correlation.diff()

    correlation_list = correlation_over_time(returns_for_correlation, **kwargs)

    return correlation_list


def empty_correlation_list() -> CorrelationList:
    empty_estimate = correlationEstimate(np.empty((0, 0)), columns=[])

    return CorrelationList(
        corr_list=[empty_estimate],
        column_names=[],
        fit_dates=listOfFittingDates(),
    )


def correlation_over_time(
    data_for_correlation: pd.DataFrame,
    date_method="expanding",
    rollyears=20,
    interval_frequency: str = "12M",
    **kwargs,
) -> CorrelationList:
    column_names = list(data_for_correlation.columns)

    # Generate time periods
    fit_dates = generate_fitting_dates(
        data_for_correlation,
        date_method=date_method,
        rollyears=rollyears,
        interval_frequency=interval_frequency,
    )

    progress = progressBar(len(fit_dates), "Estimating correlations")

    correlation_estimator_for_one_period = correlationEstimator(
        data_for_correlation, **kwargs
    )

    corr_list = []
    # Now for each time period, estimate correlation
    for fit_period in fit_dates:
        progress.iterate()
        corrmat = correlation_estimator_for_one_period.calculate_estimate_for_period(
            fit_period
        )
        corr_list.append(corrmat)

    correlation_list = CorrelationList(
        corr_list=corr_list, column_names=column_names, fit_dates=fit_dates
    )

    return correlation_list
