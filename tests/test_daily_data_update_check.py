"""
日更链路数据面校验的回归测试（FIR-162）。

校验脚本要能：从日志里数出被拒的尖峰合约、找出没有采样合约的品种、
发现 multiple prices 落后合约价格的品种，并在有异常时非零退出。
"""

import datetime

import pandas as pd

from sysinit.henrik.check_daily_data_update import (
    default_log_path,
    instruments_without_sampling_contracts,
    main,
    spike_rejections_from_log,
    stale_multiple_prices,
)

SPIKE_LINE = (
    "2026-09-27 08:01:16 DEBUG Update-Historical-Prices "
    "{'component': 'parquetFuturesContractPriceData', 'instrument_code': 'MILLWHEAT', "
    "'contract_date': '20261200'} Price has moved too much - will need to manually check"
)
NO_SAMPLING_LINE = (
    "2026-09-27 08:09:00 WARNING Update-Historical-Prices "
    "{'instrument_code': 'WHEAT-ASX'} No contracts marked for sampling for WHEAT-ASX"
)


def _write_log(tmp_path, lines):
    log_file = tmp_path / "update_20260927.log"
    log_file.write_text("\n".join(lines) + "\n")
    return str(log_file)


def test_spike_lines_are_deduplicated_by_contract(tmp_path):
    log_file = _write_log(
        tmp_path, [SPIKE_LINE, SPIKE_LINE, SPIKE_LINE, NO_SAMPLING_LINE]
    )

    pairs, total_lines = spike_rejections_from_log(log_file)

    assert pairs == [("MILLWHEAT", "20261200")]
    assert total_lines == 3


def test_instruments_without_sampling_contracts_are_reported(tmp_path):
    repeated = NO_SAMPLING_LINE.replace("WHEAT-ASX", "AUS10")
    log_file = _write_log(tmp_path, [NO_SAMPLING_LINE, repeated, SPIKE_LINE])

    assert instruments_without_sampling_contracts(log_file) == ["WHEAT-ASX", "AUS10"]


def test_default_log_path_prefers_todays_log_then_latest(tmp_path):
    latest = tmp_path / "update_20260925.log"
    today = tmp_path / "update_20260927.log"
    latest.write_text("old\n")

    assert default_log_path(str(tmp_path), today=datetime.date(2026, 9, 27)) == str(latest)

    today.write_text("new\n")
    assert default_log_path(str(tmp_path), today=datetime.date(2026, 9, 27)) == str(today)


class _FakeDiagPrices:
    def __init__(self, multiple_last, contract_last):
        self._multiple_last = multiple_last
        self._contract_last = contract_last

    def get_multiple_prices(self, instrument_code):
        return pd.DataFrame(
            {"PRICE": [1.0]}, index=pd.DatetimeIndex([self._multiple_last])
        )

    @property
    def db_futures_contract_price_data(self):
        return self

    def get_merged_prices_for_instrument(self, instrument_code):
        class _Merged:
            def final_prices(_self):
                return {
                    "20261200": pd.Series(
                        [1.0], index=pd.DatetimeIndex([self._contract_last])
                    )
                }

        return _Merged()


def test_stale_multiple_prices_are_flagged_past_the_tolerance():
    fresh = _FakeDiagPrices("2026-09-27", "2026-09-27")
    stale = _FakeDiagPrices("2026-09-10", "2026-09-27")
    diag_prices = {"FRESH": fresh, "STALE": stale}

    stale_list = stale_multiple_prices(
        _KeyedDiagPrices(diag_prices), ["FRESH", "STALE"], max_stale_days=7
    )

    assert [row[0] for row in stale_list] == ["STALE"]
    assert stale_list[0][3] == "末端落后"


class _KeyedDiagPrices:
    def __init__(self, by_instrument):
        self._by_instrument = by_instrument

    def get_multiple_prices(self, instrument_code):
        return self._by_instrument[instrument_code].get_multiple_prices(instrument_code)

    @property
    def db_futures_contract_price_data(self):
        return self

    def get_merged_prices_for_instrument(self, instrument_code):
        return self._by_instrument[
            instrument_code
        ].get_merged_prices_for_instrument(instrument_code)


def test_main_fails_on_rejected_spikes(tmp_path):
    log_file = _write_log(tmp_path, [SPIKE_LINE])

    assert main(["--log", log_file, "--skip-tail-check"]) == 1


def test_main_passes_on_clean_log(tmp_path):
    log_file = _write_log(tmp_path, [NO_SAMPLING_LINE])

    assert main(["--log", log_file, "--skip-tail-check"]) == 0


def test_main_reports_missing_log(tmp_path):
    assert main(["--log", str(tmp_path / "nope.log"), "--skip-tail-check"]) == 1
