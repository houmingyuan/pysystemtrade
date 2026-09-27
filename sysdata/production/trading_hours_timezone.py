"""
让交易时间配置可以直接写「交易所时区 + 交易所当地时段」，由代码换算成本机时间。

配置写法（`private_config_trading_hours.yaml` / `ib_config_trading_hours.yaml`）：

```yaml
# 新写法：时间按交易所当地时区给，时区用 IANA 名称
Hongkong:
  timezone: Asia/Hong_Kong
  hours:
    - '09:00'      # 单段可以直接写开、收盘
    - '17:00'

US/Central:
  timezone: America/Chicago
  hours:           # 多段用嵌套列表（这里刻意演示两段）
    - - '08:30'
      - '13:20'

# 旧写法仍然兼容：直接给本机时间的时段（不加换算）
Japan:
  - '09:00'
  - '14:00'
```

换算规则：

* 每个 weekday 的时段，取该 weekday 在交易所时区的「下一个发生日」作为代表日期，
  用 `zoneinfo` 换算到本机时区（因此交易所的夏令时会自动被正确处理）；
* 换算后如果跨越本机午夜，会按本机日期拆成多段（`23:59:59` / `00:00` 分界），
  并把每一段归到对应的**本机** weekday；
* 结果是一个「本机 weekday → 时段列表」的 dict，交给原来的解析器使用。
"""

import datetime
from calendar import day_name
from typing import List, Optional
from zoneinfo import ZoneInfo

from syscore.dateutils import time_from_string, time_to_string

WEEKDAY_NAMES = list(day_name)
ONE_DAY = datetime.timedelta(days=1)
ONE_SECOND = datetime.timedelta(seconds=1)


def is_timezone_aware_entry(spec) -> bool:
    return isinstance(spec, dict) and "timezone" in spec


def hours_spec_from_timezone_aware_entry(spec) -> object:
    """取出时区写法里的时段部分：优先 'hours'，否则把除 timezone 以外的键当作时段定义。"""
    if "hours" in spec:
        return spec["hours"]
    return {key: value for key, value in spec.items() if key != "timezone"}


def convert_hours_to_local_time(
    hours_spec,
    timezone_name: str,
    local_timezone: Optional[datetime.tzinfo] = None,
    reference_date: Optional[datetime.date] = None,
) -> dict:
    """
    把「交易所当地时区」的周表换算成本机时间的周表（按本机日期拆段）。

    :param reference_date: 计算「该 weekday 的下一个发生日」时的起点，默认今天（测试可注入）
    """
    exchange_timezone = ZoneInfo(timezone_name)
    if local_timezone is None:
        local_timezone = _system_local_timezone()

    hours_by_weekday = _normalise_to_weekdays(hours_spec)
    if reference_date is None:
        today_in_exchange = datetime.datetime.now(exchange_timezone).date()
    else:
        today_in_exchange = reference_date

    converted = {}
    for weekday_name in WEEKDAY_NAMES:
        sessions_this_weekday = _sessions_from_spec(hours_by_weekday[weekday_name])
        local_sessions_by_weekday = {}
        for open_string, close_string in sessions_this_weekday:
            reference_date = _next_date_for_weekday(today_in_exchange, weekday_name)
            open_datetime = datetime.datetime.combine(
                reference_date, time_from_string(open_string), tzinfo=exchange_timezone
            )
            close_datetime = datetime.datetime.combine(
                reference_date, time_from_string(close_string), tzinfo=exchange_timezone
            )
            if close_datetime <= open_datetime:
                close_datetime = close_datetime + ONE_DAY

            for local_weekday, local_session in _split_into_local_days(
                open_datetime.astimezone(local_timezone),
                close_datetime.astimezone(local_timezone),
            ):
                local_sessions_by_weekday.setdefault(local_weekday, []).append(local_session)

        for local_weekday, sessions in local_sessions_by_weekday.items():
            converted.setdefault(local_weekday, []).extend(sessions)

    for weekday_name in WEEKDAY_NAMES:
        converted.setdefault(weekday_name, [])

    return converted


def _system_local_timezone() -> datetime.tzinfo:
    return datetime.datetime.now().astimezone().tzinfo


def _normalise_to_weekdays(hours_spec) -> dict:
    if isinstance(hours_spec, list):
        return {weekday_name: hours_spec for weekday_name in WEEKDAY_NAMES}

    return {
        weekday_name: hours_spec.get(weekday_name, [])
        for weekday_name in WEEKDAY_NAMES
    }


def _sessions_from_spec(spec) -> List[tuple]:
    """把时段定义统一成 [(open, close), ...]。空列表 = 当天不交易。"""
    if not spec:
        return []

    if not isinstance(spec[0], list):
        # 单段：['09:00', '17:00']
        return [(spec[0], spec[1])]

    return [(one_session[0], one_session[1]) for one_session in spec]


def _next_date_for_weekday(today: datetime.date, weekday_name: str) -> datetime.date:
    target_weekday = WEEKDAY_NAMES.index(weekday_name)
    days_ahead = (target_weekday - today.weekday()) % 7
    return today + datetime.timedelta(days=days_ahead)


def _split_into_local_days(
    open_local: datetime.datetime, close_local: datetime.datetime
) -> List[tuple]:
    """把 [open_local, close_local] 按本机午夜拆成 [(weekday_name, [open, close]), ...]。"""
    pieces = []
    start = open_local
    while True:
        midnight_after_start = datetime.datetime.combine(
            start.date() + ONE_DAY, datetime.time(0, 0), tzinfo=start.tzinfo
        )
        end_of_day = midnight_after_start - ONE_SECOND
        end = min(close_local, end_of_day)
        if end > start:
            pieces.append(
                (day_name[start.weekday()], [time_to_string(start.time()), time_to_string(end.time())])
            )
        if close_local <= end_of_day:
            break
        start = midnight_after_start

    return pieces
