"""
数据修复的回归测试（FIR-137 / FIR-127）：

1. multiple prices 构建出口会把「末端 PRICE 为空」的尾行截掉；
2. 合并文件被重建时，只存在于合并文件里的历史不会丢（历史行数不得减少）。
"""

import datetime

import pandas as pd

from sysinit.futures.build_multiple_prices_from_raw_data import (
    _trim_trailing_rows_without_price,
)
from sysproduction.update_historical_prices import _keep_history_only_in_merged_file


def _multiple_prices_row(price, forward, contract="20261200"):
    return dict(
        PRICE=price,
        FORWARD=forward,
        CARRY=forward,
        PRICE_CONTRACT=contract,
        FORWARD_CONTRACT="20270100",
        CARRY_CONTRACT="20270100",
    )


def test_trailing_rows_without_price_are_trimmed():
    index = pd.to_datetime(["2026-09-24", "2026-09-25", "2026-09-26"])
    data = pd.DataFrame(
        [
            _multiple_prices_row(100.0, 101.0),
            _multiple_prices_row(101.0, 102.0),
            _multiple_prices_row(float("nan"), 103.0),  # 前端合约没有 09-26 的价格
        ],
        index=index,
    )

    trimmed = _trim_trailing_rows_without_price(data)

    assert len(trimmed) == 2
    assert trimmed.index[-1] == pd.Timestamp("2026-09-25")


def test_trailing_trim_keeps_data_when_last_price_present():
    index = pd.to_datetime(["2026-09-25", "2026-09-26"])
    data = pd.DataFrame(
        [_multiple_prices_row(100.0, 101.0), _multiple_prices_row(101.0, 102.0)],
        index=index,
    )

    assert len(_trim_trailing_rows_without_price(data)) == 2


class _FakeDiagPrices:
    def __init__(self, existing):
        self._existing = existing

    def get_merged_prices_for_contract_object(self, contract_object):
        return self._existing


def test_history_only_in_merged_file_is_kept():
    # 库里（合并文件）有 2018 年以来的历史
    old_index = pd.to_datetime(["2018-10-03", "2026-09-25"])
    existing = pd.DataFrame(
        dict(OPEN=[1.0, 2.0], HIGH=[1.0, 2.0], LOW=[1.0, 2.0], FINAL=[1.0, 2.0], VOLUME=[0.0, 10.0]),
        index=old_index,
    )

    # 分频文件只覆盖最近两天 → 重建出来的合并结果只有 2 行（其中一天是新的）
    new_index = pd.to_datetime(["2026-09-25", "2026-09-26"])
    rebuilt = pd.DataFrame(
        dict(OPEN=[3.0, 4.0], HIGH=[3.0, 4.0], LOW=[3.0, 4.0], FINAL=[3.0, 4.0], VOLUME=[5.0, 6.0]),
        index=new_index,
    )

    merged = _keep_history_only_in_merged_file(
        _FakeDiagPrices(existing), contract_object=None, merged_prices=rebuilt
    )

    # 2018-10-03 的历史必须保留，且 09-25 用新数据覆盖
    assert pd.Timestamp("2018-10-03") in merged.index
    assert merged.loc[pd.Timestamp("2026-09-25"), "FINAL"] == 3.0
    assert len(merged) == 3


def test_history_guard_handles_missing_existing_data():
    rebuilt = pd.DataFrame(
        dict(OPEN=[1.0], HIGH=[1.0], LOW=[1.0], FINAL=[1.0], VOLUME=[1.0]),
        index=pd.to_datetime(["2026-09-26"]),
    )

    class _EmptyDiagPrices:
        def get_merged_prices_for_contract_object(self, contract_object):
            return pd.DataFrame()

    merged = _keep_history_only_in_merged_file(
        _EmptyDiagPrices(), contract_object=None, merged_prices=rebuilt
    )

    assert len(merged) == 1
