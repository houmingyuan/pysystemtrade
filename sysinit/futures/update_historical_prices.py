from sysdata.config.production_config import get_production_config
from syscore.fileutils import resolve_path_and_filename_for_package
from sysdata.csv.csv_futures_contract_prices import ConfigCsvFuturesPrices
from sysinit.futures.contract_prices_from_split_freq_csv_to_db import (
    init_db_with_split_freq_csv_prices_for_code,
)
from sysdata.config.control_config import get_control_config
BARCHART_CONFIG = ConfigCsvFuturesPrices(
    input_date_index_name="Time",
    input_skiprows=0,
    input_skipfooter=0,
    input_date_format="%Y-%m-%dT%H:%M:%S%z",
    input_column_mapping=dict(
        OPEN="Open", HIGH="High", LOW="Low", FINAL="Close", VOLUME="Volume"
    ),
)


# get instrument list from config
control_config = get_control_config()
barchart_config = control_config.get_element_or_default("barchart", [])
datapath = barchart_config["path"]
instrument_list = barchart_config["download_list"]

for contract_code in instrument_list:
    # import prices for a single instrument
    init_db_with_split_freq_csv_prices_for_code(contract_code, datapath=datapath, csv_config=BARCHART_CONFIG)
