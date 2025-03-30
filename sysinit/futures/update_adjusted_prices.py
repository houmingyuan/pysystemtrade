from sysinit.futures.adjustedprices_from_db_multiple_to_db import process_adjusted_prices_all_instruments
from syscore.constants import arg_not_supplied

if __name__ == "__main__":
    process_adjusted_prices_all_instruments(
        csv_adj_data_path=arg_not_supplied, ADD_TO_DB=True, ADD_TO_CSV=False
    )
