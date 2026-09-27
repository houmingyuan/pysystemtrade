"""
IB 交易时段解析的「按天裁剪」回归测试。

规则（用户 2026-09-27 明确）：
    * 一天里的第一段：开盘 +1 小时，收盘不变
    * 一天里的最后一段：收盘 -1 小时，开盘不变
    * 中间段：不动
    一天只有一段时，首尾是同一段 → 开盘 +1 且收盘 -1。
"""

import datetime

from sysbrokers.IB.ib_trading_hours import parse_trading_hours_string


def _hours(raw: str):
    return [
        (session.opening_time.strftime("%d/%m %H:%M"), session.closing_time.strftime("%d/%m %H:%M"))
        for session in parse_trading_hours_string(raw, adjustment_hours=0)
    ]


def test_three_sessions_only_first_open_and_last_close_are_trimmed():
    # 香港：早盘 / 午盘 / 夜盘（夜盘跨到次日）
    raw = (
        "20260928:0915-20260928:1200;"
        "20260928:1300-20260928:1630;"
        "20260928:1700-20260929:0300"
    )

    assert _hours(raw) == [
        ("28/09 10:15", "28/09 12:00"),  # 第一段：开盘 +1
        ("28/09 13:00", "28/09 16:30"),  # 中间段：不动
        ("28/09 17:00", "29/09 02:00"),  # 最后一段：收盘 -1
    ]


def test_single_session_gets_both_trims():
    raw = "20260928:0800-20260928:1900"

    assert _hours(raw) == [("28/09 09:00", "28/09 18:00")]


def test_two_sessions_first_open_and_last_close_trimmed():
    # 美盘谷物：同一天里日盘 + 隔夜盘
    raw = "20260928:1900-20260929:0745;20260928:0830-20260928:1320"

    assert _hours(raw) == [
        ("28/09 09:30", "28/09 13:20"),
        ("28/09 19:00", "29/09 06:45"),
    ]


def test_middle_sessions_untouched_with_many_sessions():
    raw = (
        "20260928:0100-20260928:0300;"
        "20260928:0500-20260928:0700;"
        "20260928:0900-20260928:1100;"
        "20260928:1300-20260928:1500"
    )

    assert _hours(raw) == [
        ("28/09 02:00", "28/09 03:00"),
        ("28/09 05:00", "28/09 07:00"),
        ("28/09 09:00", "28/09 11:00"),
        ("28/09 13:00", "28/09 14:00"),
    ]


def test_closed_days_are_skipped():
    raw = "20260927:CLOSED;20260928:0800-20260928:1900"

    assert _hours(raw) == [("28/09 09:00", "28/09 18:00")]
