from syscore.constants import arg_not_supplied
from sysinit.futures.multipleprices_from_db_prices_and_csv_calendars_to_db import process_multiple_prices_all_instruments

if __name__ == "__main__":
    csv_multiple_data_path = arg_not_supplied

    # only change if you have written the files elsewhere
    csv_roll_data_path = arg_not_supplied

    # modify flags as required
    process_multiple_prices_all_instruments(
        csv_multiple_data_path=csv_multiple_data_path,
        csv_roll_data_path=csv_roll_data_path,
    )