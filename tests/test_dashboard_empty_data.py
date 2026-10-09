"""
Dashboard / reporting 空数据回归测试（FIR-223）。

系统早期阶段没有持仓、没有采样价差数据，个别品种还缺合约数据时，
/risk、/costs、/rolls 不应该因为空数据或单个品种报错而 500。
"""

import pandas as pd

from syscore.interactive.progress_bar import progressBar
from sysquant.estimators.correlation_over_time import (
    correlation_over_time_for_returns,
    empty_correlation_list,
)
from sysproduction.reporting.data import costs as costs_module
from sysproduction.reporting.data.rolls import error_roll_data_for_instrument
from sysproduction.reporting.formatting import nice_format_instrument_risk_table


def test_progress_bar_with_zero_range_does_not_divide_by_zero():
    bar = progressBar(0)

    bar.iterate()
    bar.close()


def test_correlation_over_time_for_returns_with_no_instruments():
    empty_returns = pd.DataFrame()

    correlation_list = correlation_over_time_for_returns(empty_returns)

    corr_matrix = correlation_list.most_recent_correlation_before_date()
    assert corr_matrix.size == 0
    assert list(corr_matrix.as_pd().columns) == []


def test_cluster_empty_correlation_matrix_is_identity():
    from sysproduction.reporting.data.risk import cluster_correlation_matrix

    empty_matrix = empty_correlation_list().most_recent_correlation_before_date()

    assert cluster_correlation_matrix(empty_matrix).size == 0


def test_sampling_costs_with_no_spread_data_returns_empty_series(monkeypatch):
    class _FakeDiagPrices:
        def __init__(self, data):
            pass

        def get_list_of_instruments_with_spread_data(self):
            return []

    monkeypatch.setattr(costs_module, "diagPrices", _FakeDiagPrices)

    sampling_costs, sample_count = costs_module.get_average_half_spread_from_sampling(
        None, start_date=None, end_date=None
    )

    assert sampling_costs.empty
    assert sample_count.empty


def test_error_roll_data_has_expected_shape():
    error_data = error_roll_data_for_instrument("COTTON", ValueError("boom"))

    assert "Data error" in error_data["status"]
    assert error_data["contract_volume_fwd"] == 0
    for key in ["roll_expiry", "price_expiry", "carry_expiry", "relative_volume_fwd"]:
        assert pd.isna(error_data[key])


def test_nice_format_instrument_risk_table_handles_empty():
    assert nice_format_instrument_risk_table(pd.DataFrame()).empty
