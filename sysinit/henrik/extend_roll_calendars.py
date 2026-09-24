"""
Safely extend existing roll calendars forward to current date.

Unlike fix_roll_calendars.py (which regenerates from scratch and can break
calendars with sparse early data), this script:
1. Loads the existing roll calendar
2. Generates new entries from the last date forward
3. Appends only the new entries

This is the SAFER option for calendars that work but need updating.

Usage:
    python sysinit/henrik/extend_roll_calendars.py --detect
    python sysinit/henrik/extend_roll_calendars.py --extend
    python sysinit/henrik/extend_roll_calendars.py --extend --instrument HEATOIL
"""

import argparse
import sys
from datetime import datetime

import pandas as pd

from sysobjects.roll_calendars import rollCalendar
from sysdata.csv.csv_roll_calendars import csvRollCalendarData
from sysdata.csv.csv_roll_parameters import csvRollParametersData
from sysproduction.data.prices import diagPrices


ROLL_CALENDAR_PATH = "data/futures/roll_calendars_csv"

# Extend if roll calendar ends more than this many days before contract data ends
EXTEND_THRESHOLD_DAYS = 60


def get_diag_prices():
    """Lazy load diagPrices."""
    return diagPrices()


def detect_needs_extension(
    diag_prices=None,
    threshold_days: int = EXTEND_THRESHOLD_DAYS,
    quiet: bool = False,
) -> list[dict]:
    """
    Detect instruments where roll calendar ends before contract data ends.
    These can be safely extended forward.
    """
    if diag_prices is None:
        diag_prices = get_diag_prices()

    contract_prices = diag_prices.db_futures_contract_price_data
    instruments = contract_prices.get_list_of_instrument_codes_with_merged_price_data()

    roll_cal_data = csvRollCalendarData(ROLL_CALENDAR_PATH)

    needs_extension = []

    for instrument in instruments:
        try:
            # Get contract data end
            dict_of_prices = contract_prices.get_merged_prices_for_instrument(instrument)
            if len(dict_of_prices) == 0:
                continue

            contracts = sorted(dict_of_prices.keys())
            last_contract_prices = dict_of_prices[contracts[-1]]
            contract_end = last_contract_prices.index.max()

            # Get roll calendar end
            try:
                roll_cal = roll_cal_data.get_roll_calendar(instrument)
                if len(roll_cal) == 0:
                    continue
                roll_end = roll_cal.index[-1]
            except Exception:
                continue

            # Calculate gap
            gap_days = (contract_end - roll_end).days

            if gap_days > threshold_days:
                needs_extension.append({
                    "instrument": instrument,
                    "roll_cal_end": roll_end.strftime("%Y-%m-%d"),
                    "contract_end": contract_end.strftime("%Y-%m-%d"),
                    "gap_days": gap_days,
                })

        except Exception as e:
            if not quiet:
                print(f"  Warning: Could not check {instrument}: {e}")
            continue

    # Sort by gap size
    needs_extension.sort(key=lambda x: -x["gap_days"])

    return needs_extension


def extend_roll_calendar(
    instrument_code: str,
    diag_prices=None,
    quiet: bool = False,
) -> bool:
    """
    Extend roll calendar forward from its last entry.
    Does NOT modify historical entries.
    """
    if diag_prices is None:
        diag_prices = get_diag_prices()

    if not quiet:
        print(f"\n{'='*60}")
        print(f"EXTENDING ROLL CALENDAR: {instrument_code}")
        print("=" * 60)

    # Load existing calendar
    csv_roll_calendars = csvRollCalendarData(ROLL_CALENDAR_PATH)
    try:
        existing_calendar = csv_roll_calendars.get_roll_calendar(instrument_code)
        if not quiet:
            print(f"  Existing calendar: {len(existing_calendar)} entries")
            print(f"  Last entry: {existing_calendar.index[-1]}")
    except Exception as e:
        print(f"  ERROR: Cannot load existing calendar: {e}")
        return False

    # Get roll parameters
    roll_params_data = csvRollParametersData()
    try:
        roll_parameters = roll_params_data.get_roll_parameters(instrument_code)
    except Exception as e:
        print(f"  ERROR: Cannot get roll parameters: {e}")
        return False

    # Get contract price data
    contract_prices = diag_prices.db_futures_contract_price_data
    dict_of_all_prices = contract_prices.get_merged_prices_for_instrument(instrument_code)

    if len(dict_of_all_prices) == 0:
        print(f"  ERROR: No price data")
        return False

    dict_of_final_prices = dict_of_all_prices.final_prices()

    # Get last roll info
    last_roll_date = existing_calendar.index[-1]
    last_current = existing_calendar.iloc[-1]["current_contract"]

    if not quiet:
        print(f"  Last roll: {last_roll_date}, contract {last_current}")

    # Filter prices to only those after the last roll
    filtered_prices = {}
    for contract, prices in dict_of_final_prices.items():
        if int(contract) >= int(last_current):
            future_prices = prices[prices.index > last_roll_date]
            if len(future_prices) > 0:
                filtered_prices[contract] = future_prices

    if len(filtered_prices) == 0:
        if not quiet:
            print(f"  No new price data after {last_roll_date}")
        return True  # Not an error, just nothing to do

    if not quiet:
        print(f"  Found {len(filtered_prices)} contracts after last roll")

    # Generate new roll entries
    try:
        from sysobjects.dict_of_futures_per_contract_prices import dictFuturesContractFinalPrices

        new_prices_dict = dictFuturesContractFinalPrices(filtered_prices)

        new_calendar = rollCalendar.create_from_prices(
            new_prices_dict, roll_parameters
        )

        if len(new_calendar) == 0:
            if not quiet:
                print(f"  No new roll entries generated")
            return True

        # Filter to only entries after existing calendar
        new_entries = new_calendar[new_calendar.index > last_roll_date]

        if len(new_entries) == 0:
            if not quiet:
                print(f"  No new entries after {last_roll_date}")
            return True

        if not quiet:
            print(f"  Generated {len(new_entries)} new roll entries")
            print(f"  New range: {new_entries.index[0]} to {new_entries.index[-1]}")

        # Combine existing + new
        combined = pd.concat([existing_calendar, new_entries])
        combined = combined.sort_index()
        combined = combined[~combined.index.duplicated(keep="first")]

        extended_calendar = rollCalendar(combined)

        if not quiet:
            print(f"  Extended calendar: {len(extended_calendar)} entries")

    except Exception as e:
        print(f"  ERROR generating new entries: {e}")
        return False

    # Save
    try:
        csv_roll_calendars.add_roll_calendar(
            instrument_code, extended_calendar, ignore_duplication=True
        )
        if not quiet:
            print(f"  Saved to {ROLL_CALENDAR_PATH}/{instrument_code}.csv")
    except Exception as e:
        print(f"  ERROR saving: {e}")
        return False

    return True


def rebuild_prices(instrument_code: str, quiet: bool = False) -> bool:
    """Rebuild multiple and adjusted prices after extending calendar."""
    if not quiet:
        print(f"\n  Rebuilding prices...")

    try:
        from sysinit.futures.build_multiple_prices import (
            process_single_instrument as build_multiple,
        )
        from sysinit.futures.build_adjusted_prices import (
            process_single_instrument as build_adjusted,
        )

        success, result = build_multiple(instrument_code)
        if not success:
            print(f"  ERROR building multiple prices: {result}")
            return False
        if not quiet:
            print(f"  Multiple prices: {result} rows")

        success, result = build_adjusted(instrument_code)
        if not success:
            print(f"  ERROR building adjusted prices: {result}")
            return False
        if not quiet:
            print(f"  Adjusted prices: {result} rows")

        return True

    except Exception as e:
        print(f"  ERROR: {e}")
        return False


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Safely extend roll calendars forward"
    )
    parser.add_argument(
        "--detect",
        action="store_true",
        help="Detect calendars that need extension",
    )
    parser.add_argument(
        "--extend",
        action="store_true",
        help="Extend calendars forward",
    )
    parser.add_argument(
        "--instrument", "-i",
        help="Extend specific instrument only",
    )
    parser.add_argument(
        "--no-rebuild",
        action="store_true",
        help="Skip rebuilding multiple/adjusted prices",
    )
    parser.add_argument(
        "--quiet", "-q",
        action="store_true",
        help="Quiet mode",
    )

    args = parser.parse_args()

    if not args.detect and not args.extend:
        parser.print_help()
        print("\nError: Must specify --detect or --extend")
        return 1

    if args.detect:
        if not args.quiet:
            print("=" * 60)
            print("DETECTING CALENDARS THAT NEED EXTENSION")
            print("=" * 60)

        needs_ext = detect_needs_extension(quiet=args.quiet)

        if not needs_ext:
            print("All roll calendars are up to date!")
            return 0

        print(f"Found {len(needs_ext)} instruments that need extension:\n")
        print(f"{'Instrument':20} {'Roll Cal End':15} {'Contract End':15} {'Gap (days)'}")
        print("-" * 65)
        for n in needs_ext:
            print(f"{n['instrument']:20} {n['roll_cal_end']:15} {n['contract_end']:15} {n['gap_days']}")

        print(f"\nTo extend these, run:")
        print(f"  python sysinit/henrik/extend_roll_calendars.py --extend")
        return 0

    if args.extend:
        diag_prices = get_diag_prices()

        if args.instrument:
            instruments = [args.instrument]
        else:
            needs_ext = detect_needs_extension(diag_prices, quiet=True)
            instruments = [n["instrument"] for n in needs_ext]

        if not instruments:
            print("No instruments need extension!")
            return 0

        if not args.quiet:
            print("=" * 60)
            print("EXTENDING ROLL CALENDARS")
            print("=" * 60)
            print(f"Instruments to extend: {len(instruments)}")

        results = {}
        for i, instrument in enumerate(instruments, 1):
            if not args.quiet:
                print(f"\n[{i}/{len(instruments)}] {instrument}...")

            success = extend_roll_calendar(instrument, diag_prices, args.quiet)

            if success and not args.no_rebuild:
                success = rebuild_prices(instrument, args.quiet)

            results[instrument] = success

        # Summary
        print("\n" + "=" * 60)
        print("SUMMARY")
        print("=" * 60)

        extended = [k for k, v in results.items() if v]
        failed = [k for k, v in results.items() if not v]

        if extended:
            print(f"\nEXTENDED ({len(extended)}): {', '.join(extended)}")
        if failed:
            print(f"\nFAILED ({len(failed)}): {', '.join(failed)}")

        return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
