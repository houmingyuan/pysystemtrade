"""
Build multiple prices for ALL instruments, handling errors gracefully.

This is a batch version that continues on errors and reports failures at the end.
"""
from syscore.constants import arg_not_supplied
from sysobjects.dict_of_futures_per_contract_prices import dictFuturesContractFinalPrices
import datetime
import pandas as pd

from sysproduction.data.prices import diagPrices
from sysobjects.rolls import rollParameters, contractDateWithRollParameters
from sysobjects.contract_dates_and_expiries import contractDate
from sysdata.csv.csv_roll_calendars import csvRollCalendarData
from sysdata.csv.csv_multiple_prices import csvFuturesMultiplePricesData
from sysdata.csv.csv_roll_parameters import csvRollParametersData
from sysinit.futures.build_roll_calendars import adjust_to_price_series
from sysobjects.multiple_prices import futuresMultiplePrices


diag_prices = diagPrices()


def _get_data_inputs(csv_roll_data_path, csv_multiple_data_path):
    csv_roll_calendars = csvRollCalendarData(csv_roll_data_path)
    db_individual_futures_prices = diag_prices.db_futures_contract_price_data
    db_multiple_prices = diag_prices.db_futures_multiple_prices_data
    csv_multiple_prices = csvFuturesMultiplePricesData(csv_multiple_data_path)
    return (
        csv_roll_calendars,
        db_individual_futures_prices,
        db_multiple_prices,
        csv_multiple_prices,
    )


def add_phantom_row(
    roll_calendar,
    dict_of_futures_contract_prices: dictFuturesContractFinalPrices,
    roll_parameters: rollParameters,
):
    final_row = roll_calendar.iloc[-1]
    if datetime.datetime.now() < final_row.name:
        return roll_calendar
    virtual_datetime = datetime.datetime.now() + datetime.timedelta(days=5)
    current_contract_date_str = str(final_row.next_contract)
    current_contract = contractDateWithRollParameters(
        contractDate(current_contract_date_str), roll_parameters
    )
    next_contract = current_contract.next_held_contract()
    carry_contract = current_contract.carry_contract()

    list_of_contract_names = dict_of_futures_contract_prices.keys()
    try:
        assert current_contract.date_str in list_of_contract_names
    except:
        print("Can't add extra row as data missing")
        return roll_calendar

    new_row = pd.DataFrame(
        dict(
            current_contract=current_contract_date_str,
            next_contract=next_contract.date_str,
            carry_contract=carry_contract.date_str,
        ),
        index=[virtual_datetime],
    )
    roll_calendar = pd.concat([roll_calendar, new_row], axis=0)
    return roll_calendar


def adjust_roll_calendar(instrument_code, roll_calendar):
    db_prices_per_contract = diag_prices.db_futures_contract_price_data
    dict_of_prices = db_prices_per_contract.get_merged_prices_for_instrument(instrument_code)
    dict_of_futures_contract_prices = dict_of_prices.final_prices()
    roll_calendar = adjust_to_price_series(roll_calendar, dict_of_futures_contract_prices)
    return roll_calendar


def process_single_instrument(
    instrument_code,
    csv_roll_data_path=arg_not_supplied,
    csv_multiple_data_path=arg_not_supplied,
):
    """Process one instrument, return True on success, error message on failure."""
    try:
        (
            csv_roll_calendars,
            db_individual_futures_prices,
            db_multiple_prices,
            csv_multiple_prices,
        ) = _get_data_inputs(csv_roll_data_path, csv_multiple_data_path)

        dict_of_futures_contract_prices = (
            db_individual_futures_prices.get_merged_prices_for_instrument(instrument_code)
        )
        dict_of_futures_contract_closing_prices = (
            dict_of_futures_contract_prices.final_prices()
        )

        roll_calendar = csv_roll_calendars.get_roll_calendar(instrument_code)

        m = csvRollParametersData()
        roll_parameters = m.get_roll_parameters(instrument_code)

        roll_calendar = add_phantom_row(
            roll_calendar, dict_of_futures_contract_closing_prices, roll_parameters
        )

        roll_calendar = adjust_roll_calendar(instrument_code, roll_calendar)

        roll_calendar = add_phantom_row(
            roll_calendar, dict_of_futures_contract_closing_prices, roll_parameters
        )

        multiple_prices = futuresMultiplePrices.create_from_raw_data(
            roll_calendar, dict_of_futures_contract_closing_prices
        )

        db_multiple_prices.add_multiple_prices(
            instrument_code, multiple_prices, ignore_duplication=True
        )

        return True, len(multiple_prices)

    except Exception as e:
        return False, str(e)


def process_all_instruments():
    """Process all instruments, handling errors gracefully."""
    db_individual_futures_prices = diag_prices.db_futures_contract_price_data
    instrument_list = db_individual_futures_prices.get_list_of_instrument_codes_with_merged_price_data()
    instrument_list.sort()

    print(f"Processing {len(instrument_list)} instruments")
    print("=" * 60)

    successes = []
    failures = []

    for i, instrument_code in enumerate(instrument_list, 1):
        print(f"[{i}/{len(instrument_list)}] {instrument_code}...", end=" ")

        success, result = process_single_instrument(instrument_code)

        if success:
            print(f"OK ({result} rows)")
            successes.append(instrument_code)
        else:
            print(f"FAILED")
            failures.append((instrument_code, result))

    print("\n" + "=" * 60)
    print(f"COMPLETE: {len(successes)} success, {len(failures)} failed")

    if failures:
        print("\nFailed instruments:")
        for inst, error in failures:
            # Truncate long error messages
            error_short = error[:100] + "..." if len(error) > 100 else error
            print(f"  {inst}: {error_short}")

    return successes, failures


if __name__ == "__main__":
    input("This will build multiple prices for all instruments. Press Enter to continue (Ctrl-C to abort)")
    successes, failures = process_all_instruments()
