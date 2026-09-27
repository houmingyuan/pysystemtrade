"""
按日期对齐价格（align_prices_by_date）的回归测试（FIR-161）。

价格库里日线口径混用（Norgate/CSV 是 00:00、IB 是 23:00），构建 multiple prices 前
必须先对齐到「日期」。同日多条要保留时间戳最大的一条；乱序输入也不能保留旧行。
"""

import pandas as pd

from sysinit.futures.build_roll_calendars import align_prices_by_date


def test_same_day_rows_keep_the_latest_timestamp_even_when_unsorted():
    raw = {
        "20261200": pd.Series(
            [3.0, 1.0, 2.0],
            index=pd.to_datetime(
                ["2026-09-25 23:00", "2026-09-25 00:00", "2026-09-25 13:00"]
            ),
        )
    }

    aligned = align_prices_by_date(raw)["20261200"]

    assert len(aligned) == 1
    assert aligned.index.tolist() == list(pd.to_datetime(["2026-09-25"]))
    assert aligned.iloc[0] == 3.0


def test_mixed_timestamps_are_normalised_to_midnight_and_sorted():
    raw = {
        "20261200": pd.Series(
            [2.0, 1.0],
            index=pd.to_datetime(["2026-09-28 00:00", "2026-09-25 23:00"]),
        )
    }

    aligned = align_prices_by_date(raw)["20261200"]

    assert aligned.index.tolist() == list(
        pd.to_datetime(["2026-09-25", "2026-09-28"])
    )
    assert aligned.tolist() == [1.0, 2.0]


def test_multiple_contracts_are_aligned_independently():
    raw = {
        "20261200": pd.Series([1.0], index=pd.to_datetime(["2026-09-25 23:00"])),
        "20270100": pd.Series([2.0], index=pd.to_datetime(["2026-09-25 00:00"])),
    }

    aligned = align_prices_by_date(raw)

    # 两个合约换月日两侧时间戳不同（23:00 / 00:00），对齐后必须落在同一天
    assert aligned["20261200"].index.tolist() == aligned["20270100"].index.tolist()


def test_empty_input_returns_empty_alignment():
    aligned = align_prices_by_date({})

    assert len(aligned) == 0
