import datetime
from ib_async import ContractDetails as ibContractDetails

from sysdata.config.private_config import (
    get_private_config_dir,
)
from sysobjects.production.trading_hours.trading_hours import (
    tradingHours,
    listOfTradingHours,
)
from syscore.fileutils import (
    does_resolved_filename_exist,
    resolve_path_and_filename_for_package,
)
from sysdata.config.production_config import get_production_config
from sysdata.production.trading_hours import read_trading_hours
from syslogging.logger import get_logger

logger = get_logger("ib_trading_hours")

IB_CONFIG_TRADING_HOURS_FILE = "sysbrokers.IB.ib_config_trading_hours.yaml"
PRIVATE_CONFIG_TRADING_HOURS_FILE = "private_config_trading_hours.yaml"


def get_saved_trading_hours():
    private_path = resolve_path_and_filename_for_package(
        get_private_config_dir(), PRIVATE_CONFIG_TRADING_HOURS_FILE
    )
    if does_resolved_filename_exist(private_path):
        return read_trading_hours(private_path)
    else:
        default_path = resolve_path_and_filename_for_package(
            IB_CONFIG_TRADING_HOURS_FILE
        )
        return read_trading_hours(default_path)


def get_trading_hours_from_contract_details(
    ib_contract_details: ibContractDetails,
) -> listOfTradingHours:
    try:
        time_zone_id = ib_contract_details.timeZoneId
        time_zone_adjustment = get_time_difference(time_zone_id)

        trading_hours_string = ib_contract_details.tradingHours
        list_of_open_times = parse_trading_hours_string(
            trading_hours_string, adjustment_hours=time_zone_adjustment
        )
    except Exception as e:
        raise e

    return list_of_open_times


NO_ADJUSTMENTS = 0, 0
CLOSED_ALL_DAY = object()
ONE_HOUR = datetime.timedelta(hours=1)


def parse_trading_hours_string(
    trading_hours_string: str,
    adjustment_hours: int = 0,
) -> listOfTradingHours:
    """
    把 IB 的 tradingHours 字符串解析成交易时段列表，并做「按天」的安全裁剪。

    裁剪规则（先按交易所交易日分组，再在组内裁）：

    * 当天的**第一段**：开盘时间 +1 小时，收盘时间不变；
    * 当天的**最后一段**：收盘时间 -1 小时，开盘时间不变；
    * 中间的段：不做任何调整。

    单段的日子等价于旧行为（开盘 +1、收盘 -1）。之所以按天裁而不是逐段裁：
    香港这类市场一天有多段（早盘 / 午盘 / 夜盘），逐段裁会把每段两端都削掉，
    短段会被削成零长度而消失；按天裁只保留「避开开盘 1 小时与收盘 1 小时」的
    整体保护意图（用于吸收时区 / DST 换算的不精确）。
    """
    sessions_by_exchange_trading_date = {}
    for string_for_day in trading_hours_string.split(";"):
        parsed_session = parse_trading_for_day(
            string_for_day, adjustment_hours=adjustment_hours
        )
        if parsed_session is CLOSED_ALL_DAY:
            continue
        exchange_trading_date = _exchange_trading_date_from_entry(string_for_day)
        sessions_by_exchange_trading_date.setdefault(exchange_trading_date, []).append(
            parsed_session
        )

    list_of_open_times = []
    for _, sessions_today in sessions_by_exchange_trading_date.items():
        sessions_today.sort(key=lambda session: session.opening_time)
        if len(sessions_today) == 1:
            # 一天只有一段：开盘 +1、收盘 -1（首尾是同一段）
            only_session = sessions_today[0]
            sessions_today[0] = _fallback_if_trim_inverts_the_session(
                tradingHours(
                    only_session.opening_time + ONE_HOUR,
                    only_session.closing_time - ONE_HOUR,
                ),
                only_session,
                "当天唯一一段",
            )
        else:
            first_session = sessions_today[0]
            last_session = sessions_today[-1]
            sessions_today[0] = _fallback_if_trim_inverts_the_session(
                tradingHours(
                    first_session.opening_time + ONE_HOUR, first_session.closing_time
                ),
                first_session,
                "当天第一段",
            )
            sessions_today[-1] = _fallback_if_trim_inverts_the_session(
                tradingHours(
                    last_session.opening_time, last_session.closing_time - ONE_HOUR
                ),
                last_session,
                "当天最后一段",
            )
        list_of_open_times.extend(sessions_today)

    list_of_open_times = sorted(list_of_open_times, key=lambda session: session.opening_time)

    return listOfTradingHours(list_of_open_times)


def _fallback_if_trim_inverts_the_session(
    trimmed_session: tradingHours, original_session: tradingHours, description: str
) -> tradingHours:
    """
    段落短于 2 小时时，「开盘 +1 / 收盘 -1」的裁剪会把区间裁成倒挂（如 10:00 → 08:45），
    下游取交集会得到空窗口却没有任何提示。这里回退成未裁剪的原时段并打 warning。
    """
    if trimmed_session.opening_time < trimmed_session.closing_time:
        return trimmed_session

    logger.warning(
        "按天裁剪后交易时段倒挂（%s）：%s → %s；回退为未裁剪的 %s → %s"
        % (
            description,
            trimmed_session.opening_time,
            trimmed_session.closing_time,
            original_session.opening_time,
            original_session.closing_time,
        )
    )

    return original_session


def _exchange_trading_date_from_entry(string_for_day: str) -> str:
    """
    取 IB 条目的「交易所当地交易日」前缀（如 '20260928:0915-20260928:1200' → '20260928'）。

    注意：分组必须用交易所当地日期（未经时区换算），因为「一天分几段」是交易所定义的；
    换算到本机时区后日期可能整体平移，会把同一天的段拆散。
    """
    return string_for_day.split(":")[0]


def parse_trading_for_day(
    string_for_day: str, adjustment_hours: int = 0
) -> tradingHours:
    start_and_end = string_for_day.split("-")
    if len(start_and_end) == 1:
        # closed
        return CLOSED_ALL_DAY

    start_phrase = start_and_end[0]
    end_phrase = start_and_end[1]

    # 这里只做时区换算；「开盘 +1 小时 / 收盘 -1 小时」的安全裁剪在
    # parse_trading_hours_string 里按天进行（见该函数说明）
    start_dt = parse_phrase(start_phrase, adjustment_hours=adjustment_hours)

    end_dt = parse_phrase(end_phrase, adjustment_hours=adjustment_hours)

    return tradingHours(start_dt, end_dt)


def parse_phrase(
    phrase: str, adjustment_hours: int = 0, additional_adjust: int = 0
) -> datetime.datetime:
    total_adjustment = adjustment_hours + additional_adjust
    original_time = datetime.datetime.strptime(phrase, "%Y%m%d:%H%M")
    adjustment = datetime.timedelta(hours=total_adjustment)

    return original_time + adjustment


def get_GMT_offset_hours():
    # this needs to be in private_config.YAML
    # where are the defaults stored that needs to be
    # GMT_offset_hours = 0
    try:
        production_config = get_production_config()
        GMT_offset_hours = production_config.GMT_offset_hours
    except:
        raise Exception("Default is zero, have it in private_config")
    return GMT_offset_hours


def get_time_difference(time_zone_id: str) -> int:
    # Doesn't deal with DST. We will be conservative and only trade 1 hour
    # after and 1 hour before
    # confusingly, IB seem to have changed their time zone codes in 2020
    # some of these are legacy codes which could be removed
    time_diff_dict = {
        "CST (Central Standard Time)": 6,
        "MET (Middle Europe Time)": -1,
        "EST (Eastern Standard Time)": 5,
        "JST (Japan Standard Time)": -9,
        "US/Eastern": 5,
        "MET": -1,
        "EST": 5,
        "JST": -9,
        "Japan": -9,
        "US/Central": 6,
        "GB-Eire": 0,
        "Hongkong": -8,
        "Australia/NSW": -11,
        "": 0,
    }
    GMT_offset_hours = get_GMT_offset_hours()
    for k, v in time_diff_dict.items():
        time_diff_dict[k] = v + GMT_offset_hours
    diff_hours = time_diff_dict.get(time_zone_id, None)
    if diff_hours is None:
        raise Exception("Time zone '%s' not found!" % time_zone_id)

    return diff_hours
