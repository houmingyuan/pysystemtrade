"""
交易时间配置支持「交易所时区 + 交易所当地时段」的回归测试。

配置里直接写交易所当地时间和 IANA 时区名，代码负责换算到本机时间（含交易所夏令时），
跨本机午夜的时段自动拆段。
"""

import datetime
from zoneinfo import ZoneInfo

import pytest

from sysdata.production.trading_hours import _convert_entry_to_local_time_if_needed
from sysdata.production.trading_hours_timezone import (
    InvalidTradingHoursSpec,
    UnknownTimezone,
    convert_hours_to_local_time,
    is_timezone_aware_entry,
)

SHANGHAI = ZoneInfo("Asia/Shanghai")


def test_legacy_local_time_entry_is_untouched():
    legacy = ["09:00", "17:00"]

    assert is_timezone_aware_entry(legacy) is False
    assert _convert_entry_to_local_time_if_needed(legacy) == legacy


def test_hong_kong_window_is_same_clock_time_in_shanghai():
    # 香港与本机同为 UTC+8，换算后时钟时间不变
    converted = convert_hours_to_local_time(
        ["09:00", "17:00"],
        "Asia/Hong_Kong",
        local_timezone=SHANGHAI,
        reference_date=datetime.date(2026, 9, 28),
    )

    assert converted["Monday"] == [["09:00", "17:00"]]
    assert converted["Sunday"] == [["09:00", "17:00"]]


def test_us_central_window_crossing_local_midnight_is_split():
    # 芝加哥夏令时（CDT, UTC-5）：09:00-14:00 → 本机 22:00-次日 03:00，按本机午夜拆两段
    converted = convert_hours_to_local_time(
        ["09:00", "14:00"],
        "America/Chicago",
        local_timezone=SHANGHAI,
        reference_date=datetime.date(2026, 7, 20),
    )

    assert ["22:00", "23:59"] in converted["Monday"]
    assert ["00:00", "03:00"] in converted["Tuesday"]


def test_exchange_daylight_saving_is_accounted_for():
    # 同一个配置在芝加哥冬令时（CST, UTC-6）时，本机时间晚一小时
    summer = convert_hours_to_local_time(
        ["09:00", "14:00"],
        "America/Chicago",
        local_timezone=SHANGHAI,
        reference_date=datetime.date(2026, 7, 20),
    )
    winter = convert_hours_to_local_time(
        ["09:00", "14:00"],
        "America/Chicago",
        local_timezone=SHANGHAI,
        reference_date=datetime.date(2026, 1, 19),
    )

    assert summer["Monday"][0] == ["22:00", "23:59"]
    assert winter["Monday"][0] == ["23:00", "23:59"]
    # 每天都有自己的开盘段与「前一天延续过来」的尾段
    assert ["00:00", "04:00"] in winter["Tuesday"]
    assert ["00:00", "03:00"] in summer["Tuesday"]


def test_multiple_sessions_per_day_and_per_weekday_spec():
    spec = {
        "Monday": [["09:00", "12:00"], ["13:00", "16:30"]],
        "Tuesday": [],
    }

    converted = convert_hours_to_local_time(
        spec,
        "Asia/Hong_Kong",
        local_timezone=SHANGHAI,
        reference_date=datetime.date(2026, 9, 28),
    )

    assert converted["Monday"] == [["09:00", "12:00"], ["13:00", "16:30"]]
    assert converted["Tuesday"] == []
    assert converted["Sunday"] == []


def test_unknown_timezone_is_reported_by_the_converter():
    with pytest.raises(UnknownTimezone):
        convert_hours_to_local_time(
            ["09:00", "17:00"],
            "Asia/Nowhere",
            local_timezone=SHANGHAI,
            reference_date=datetime.date(2026, 9, 28),
        )


def test_unknown_timezone_entry_falls_back_to_local_time(capsys):
    # 一个条目写错时区不该让整份配置读不出来：退回按本机时间处理 + 告警
    entry = {"timezone": "Asia/Nowhere", "hours": ["09:00", "17:00"]}

    assert _convert_entry_to_local_time_if_needed(entry) == ["09:00", "17:00"]
    assert "Asia/Nowhere" in capsys.readouterr().out


def test_misspelled_hours_key_is_rejected_instead_of_silently_empty():
    with pytest.raises(InvalidTradingHoursSpec):
        _convert_entry_to_local_time_if_needed(
            {"timezone": "Asia/Hong_Kong", "hour": ["09:00", "17:00"]}
        )


def test_timezone_entry_without_hours_or_weekdays_is_rejected():
    with pytest.raises(InvalidTradingHoursSpec):
        _convert_entry_to_local_time_if_needed({"timezone": "Asia/Hong_Kong"})


def test_weekday_spec_is_accepted_without_hours_key():
    spec = {"timezone": "Asia/Hong_Kong", "Monday": ["09:00", "17:00"]}

    converted = _convert_entry_to_local_time_if_needed(spec)

    assert converted["Monday"] == [["09:00", "17:00"]]
    assert converted["Tuesday"] == []
