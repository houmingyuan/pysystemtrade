import yaml
from sysobjects.production.trading_hours.dict_of_weekly_trading_hours_any_day import (
    dictOfDictOfWeekdayTradingHours,
)
from sysdata.production.trading_hours_timezone import (
    convert_hours_to_local_time,
    hours_spec_from_timezone_aware_entry,
    is_timezone_aware_entry,
)
from syscore.fileutils import resolve_path_and_filename_for_package


def read_trading_hours(filename: str):
    resolved_filename = resolve_path_and_filename_for_package(filename)
    try:
        with open(resolved_filename, "r") as file_to_parse:
            simple_dict = yaml.load(file_to_parse, Loader=yaml.Loader)
    except:
        print("File %s not found, no saved trading hours" % filename)
        simple_dict = {}

    simple_dict = {
        entry_name: _convert_entry_to_local_time_if_needed(entry)
        for entry_name, entry in simple_dict.items()
    }

    return dictOfDictOfWeekdayTradingHours.from_simple_dict(simple_dict)


def _convert_entry_to_local_time_if_needed(entry):
    """
    支持「交易所时区 + 交易所当地时段」的写法，读取时自动换算成本机时间；
    不带 timezone 的旧写法（本机时间）原样返回。
    """
    if not is_timezone_aware_entry(entry):
        return entry

    return convert_hours_to_local_time(
        hours_spec=hours_spec_from_timezone_aware_entry(entry),
        timezone_name=entry["timezone"],
    )


def write_trading_hours(
    dict_of_dict_of_trading_hours: dictOfDictOfWeekdayTradingHours, filename: str
):
    simple_dict = dict_of_dict_of_trading_hours.to_simple_dict()
    resolved_filename = resolve_path_and_filename_for_package(filename)
    with open(resolved_filename, "w") as file_to_write_to:
        yaml.dump(simple_dict, file_to_write_to, sort_keys=False)
