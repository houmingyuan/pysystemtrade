"""
本地换月工具的回归测试（FIR-163）。

1. 按成交量重建日历时的 carry 合约必须跟着 rollconfig 的 CarryOffset 走，
   不能固定为「换月前持有」；
2. 砍日历末端时只能砍「超前换月」的行，刚换月期间成交量第一仍是旧合约的那种
   「落后」的真实换月行不能砍；
3. 失滚重建默认只在日历末尾追加换月，不能改写历史行（docs/production_migration_cn.md P7）。
"""

import pandas as pd
import pytest

from sysdata.csv.csv_roll_parameters import csvRollParametersData
from sysinit.henrik.rebuild_roll_calendar_from_volume import (
    carry_contract_for_held,
    extend_existing_calendar,
)
from sysinit.henrik.repair_front_contracts import trim_spurious_trailing_rows
from sysobjects.rolls import rollParameters

MONTHLY = "FGHJKMNQUVXZ"  # 所有月份的 priced rollcycle，便于构造用例


def _roll_calendar(rows):
    return pd.DataFrame(
        [
            dict(current_contract=current, next_contract=next_, carry_contract=current)
            for current, next_ in rows
        ],
        index=pd.date_range("2026-09-01", periods=len(rows), freq="MS"),
    )


def test_carry_offset_plus_one_uses_the_next_contract():
    roll_parameters = rollParameters(
        hold_rollcycle=MONTHLY,
        priced_rollcycle=MONTHLY,
        roll_offset_day=-5,
        carry_offset=1,
    )

    assert carry_contract_for_held(20261200, roll_parameters) == 20270100


def test_carry_offset_minus_one_uses_the_previous_contract():
    roll_parameters = rollParameters(
        hold_rollcycle=MONTHLY,
        priced_rollcycle=MONTHLY,
        roll_offset_day=-5,
        carry_offset=-1,
    )

    assert carry_contract_for_held(20261200, roll_parameters) == 20261100


def test_carry_follows_the_real_rollconfig():
    config = csvRollParametersData()

    # VIX 在 rollconfig 里是 CarryOffset=+1（carry 取下月）
    assert carry_contract_for_held(
        20261200, config.get_roll_parameters("VIX")
    ) == 20270100
    # CORN 是 CarryOffset=-1（carry 取 priced rollcycle HKNUZ 里的上一个合约：202612 → 202609）
    assert carry_contract_for_held(
        20261200, config.get_roll_parameters("CORN")
    ) == 20260900


def test_trim_keeps_real_roll_rows_when_calendar_lags_volume_leader():
    # 日历只到 20261000，但成交量第一已经是 20261200（日历落后于市场）
    roll_calendar = _roll_calendar([(20260800, 20260900), (20260900, 20261000)])

    trimmed = trim_spurious_trailing_rows(roll_calendar, front_contract=20261200)

    # 一行都不能砍（旧实现会一路砍到只剩一行然后抛「日历里没有前端合约」）
    assert len(trimmed) == 2


def test_trim_cuts_only_rows_ahead_of_the_volume_leader():
    roll_calendar = _roll_calendar(
        [(20261000, 20261100), (20261100, 20261200), (20261200, 20270100)]
    )

    trimmed = trim_spurious_trailing_rows(roll_calendar, front_contract=20261200)

    assert len(trimmed) == 2
    assert int(trimmed.iloc[-1].next_contract) == 20261200


def test_trim_raises_when_calendar_is_ahead_even_after_trimming():
    roll_calendar = _roll_calendar([(20261100, 20261200)])

    with pytest.raises(Exception):
        trim_spurious_trailing_rows(roll_calendar, front_contract=20261000)


def _dated_calendar(rows):
    """rows: (换月日, current, next)"""
    return pd.DataFrame(
        [
            dict(current_contract=current, next_contract=next_, carry_contract=current)
            for _, current, next_ in rows
        ],
        index=pd.DatetimeIndex([date for date, _, _ in rows]),
    )


def test_extend_keeps_history_and_appends_only_new_rolls():
    existing = _dated_calendar(
        [("1990-03-10", 19900300, 19900600), ("1990-06-10", 19900600, 19900900)]
    )
    # 重建结果的历史换月日不同（成交量法），另外多出一次新的换月
    rebuilt = _dated_calendar(
        [("1990-06-12", 19900600, 19900900), ("1990-09-11", 19900900, 19901200)]
    )

    result = extend_existing_calendar(existing, rebuilt)

    assert result.iloc[:2].equals(existing)
    assert list(result.next_contract) == [19900600, 19900900, 19901200]


def test_extend_without_new_rolls_returns_existing():
    existing = _dated_calendar([("2026-03-10", 20260300, 20260600)])
    rebuilt = _dated_calendar([("2026-03-12", 20260300, 20260600)])

    assert extend_existing_calendar(existing, rebuilt).equals(existing)


def test_extend_refuses_a_broken_chain():
    existing = _dated_calendar([("2026-03-10", 20260300, 20260600)])
    # 漏了 20260600 -> 20260900 这一次换月
    rebuilt = _dated_calendar([("2026-09-10", 20260900, 20261200)])

    with pytest.raises(ValueError):
        extend_existing_calendar(existing, rebuilt)


def test_extend_of_an_empty_calendar_uses_the_rebuild():
    rebuilt = _dated_calendar([("2026-03-10", 20260300, 20260600)])

    assert extend_existing_calendar(rebuilt.iloc[0:0], rebuilt).equals(rebuilt)
