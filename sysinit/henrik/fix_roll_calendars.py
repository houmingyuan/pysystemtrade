"""
Fix instruments with truncated or broken roll calendars.

This script handles two types of issues:
1. **Broken roll calendars** - Roll calendar references contracts that don't exist in data
2. **Truncated roll calendars** - Contract data exists before roll calendar starts

The solution is the same: regenerate roll calendars from actual contract price data,
then rebuild multiple prices and adjusted prices.

Usage:
    # Detect truncated roll calendars (dry run)
    python sysinit/henrik/fix_roll_calendars.py --detect

    # Detect broken roll calendars
    python sysinit/henrik/fix_roll_calendars.py --detect-broken

    # Fix all truncated
    python sysinit/henrik/fix_roll_calendars.py --fix

    # Fix specific instruments
    python sysinit/henrik/fix_roll_calendars.py --fix --instruments EUROSTX BUND CAC

    # Quiet mode for scripting
    python sysinit/henrik/fix_roll_calendars.py --fix --quiet
"""

import argparse
import sys
from pathlib import Path

import pandas as pd

from sysobjects.roll_calendars import rollCalendar
from sysdata.csv.csv_roll_calendars import csvRollCalendarData
from sysdata.csv.csv_roll_parameters import csvRollParametersData
from sysproduction.data.prices import diagPrices

# Output paths - adjust this to your PST installation
ROLL_CALENDAR_PATH = "data/futures/roll_calendars_csv"

# Minimum gap (in days) to consider a roll calendar "truncated"
MIN_GAP_DAYS = 365


def get_diag_prices():
    """Lazy load diagPrices to avoid initialization on import."""
    return diagPrices()


def detect_truncated_roll_calendars(
    min_gap_days: int = MIN_GAP_DAYS,
    diag_prices=None,
    quiet: bool = False,
) -> list[dict]:
    """
    Detect instruments where contract data exists before roll calendar starts.

    Returns list of dicts with: instrument, contracts_from, roll_cal_from, gap_years
    """
    if diag_prices is None:
        diag_prices = get_diag_prices()

    contract_prices = diag_prices.db_futures_contract_price_data

    # Get all instruments with contract prices
    instruments = contract_prices.get_list_of_instrument_codes_with_merged_price_data()

    roll_cal_data = csvRollCalendarData(ROLL_CALENDAR_PATH)

    truncated = []

    for instrument in instruments:
        try:
            # Get earliest contract
            dict_of_prices = contract_prices.get_merged_prices_for_instrument(instrument)
            if len(dict_of_prices) == 0:
                continue

            contracts = sorted(dict_of_prices.keys())
            earliest_contract = contracts[0]  # e.g., "19990600"
            earliest_dt = pd.to_datetime(str(earliest_contract)[:6] + "01", format="%Y%m%d")

            # Get roll calendar start
            try:
                roll_cal = roll_cal_data.get_roll_calendar(instrument)
                if len(roll_cal) == 0:
                    continue
                roll_start = roll_cal.index[0]
            except Exception:
                # No roll calendar file
                continue

            # Calculate gap
            gap_days = (roll_start - earliest_dt).days

            if gap_days > min_gap_days:
                truncated.append({
                    "instrument": instrument,
                    "contracts_from": str(earliest_contract)[:6],
                    "roll_cal_from": roll_start.strftime("%Y-%m"),
                    "gap_years": round(gap_days / 365, 1),
                })
        except Exception as e:
            if not quiet:
                print(f"  Warning: Could not check {instrument}: {e}")
            continue

    # Sort by gap size (largest first)
    truncated.sort(key=lambda x: -x["gap_years"])

    return truncated


def detect_broken_roll_calendars(
    diag_prices=None,
    quiet: bool = False,
) -> list[dict]:
    """
    Detect instruments where roll calendar references contracts that don't exist.

    Returns list of dicts with: instrument, missing_contracts, total_rolls
    """
    if diag_prices is None:
        diag_prices = get_diag_prices()

    contract_prices = diag_prices.db_futures_contract_price_data

    # Get all instruments with contract prices
    instruments = contract_prices.get_list_of_instrument_codes_with_merged_price_data()

    roll_cal_data = csvRollCalendarData(ROLL_CALENDAR_PATH)

    broken = []

    for instrument in instruments:
        try:
            # Get available contracts
            dict_of_prices = contract_prices.get_merged_prices_for_instrument(instrument)
            if len(dict_of_prices) == 0:
                continue

            available_contracts = set(str(c)[:6] for c in dict_of_prices.keys())

            # Get roll calendar
            try:
                roll_cal = roll_cal_data.get_roll_calendar(instrument)
                if len(roll_cal) == 0:
                    continue
            except Exception:
                continue

            # Check each roll references existing contracts
            missing = set()
            for _, row in roll_cal.iterrows():
                current = str(row["current_contract"])[:6]
                next_c = str(row["next_contract"])[:6]

                if current not in available_contracts:
                    missing.add(current)
                if next_c not in available_contracts:
                    missing.add(next_c)

            if missing:
                broken.append({
                    "instrument": instrument,
                    "missing_contracts": sorted(missing),
                    "total_rolls": len(roll_cal),
                    "missing_count": len(missing),
                })

        except Exception as e:
            if not quiet:
                print(f"  Warning: Could not check {instrument}: {e}")
            continue

    # Sort by number of missing contracts (most first)
    broken.sort(key=lambda x: -x["missing_count"])

    return broken


def regenerate_roll_calendar(
    instrument_code: str,
    diag_prices=None,
    quiet: bool = False,
    force: bool = False,
) -> bool:
    """
    Regenerate roll calendar for one instrument from actual price data.
    Returns True on success, False on failure.

    SAFETY CHECK: Will abort if the new calendar has fewer entries than the
    existing one (indicates sparse early data causing truncation). Use force=True
    to override this safety check.
    """
    if diag_prices is None:
        diag_prices = get_diag_prices()

    if not quiet:
        print(f"\n{'='*60}")
        print(f"REGENERATING ROLL CALENDAR: {instrument_code}")
        print("=" * 60)

    # Get existing roll calendar size for safety check
    csv_roll_calendars = csvRollCalendarData(ROLL_CALENDAR_PATH)
    existing_count = 0
    try:
        existing_cal = csv_roll_calendars.get_roll_calendar(instrument_code)
        existing_count = len(existing_cal)
        if not quiet:
            print(f"  Existing calendar: {existing_count} entries")
    except Exception:
        pass  # No existing calendar

    # Get roll parameters
    roll_params_data = csvRollParametersData()
    try:
        roll_parameters = roll_params_data.get_roll_parameters(instrument_code)
        if not quiet:
            print(f"  Roll parameters: hold={roll_parameters.hold_rollcycle}, "
                  f"priced={roll_parameters.priced_rollcycle}")
    except Exception as e:
        print(f"  ERROR: Cannot get roll parameters: {e}")
        return False

    # Get contract price data
    contract_prices = diag_prices.db_futures_contract_price_data
    dict_of_all_prices = contract_prices.get_merged_prices_for_instrument(instrument_code)

    if len(dict_of_all_prices) == 0:
        print(f"  ERROR: No price data for {instrument_code}")
        return False

    dict_of_final_prices = dict_of_all_prices.final_prices()
    contracts = list(dict_of_final_prices.keys())
    if not quiet:
        print(f"  Found {len(contracts)} contracts with price data")
        print(f"  Date range: {contracts[0]} to {contracts[-1]}")

    # Build roll calendar from prices
    try:
        if not quiet:
            print("  Building roll calendar from prices...")
        roll_calendar = rollCalendar.create_from_prices(
            dict_of_final_prices, roll_parameters
        )

        # Validate
        roll_calendar.check_if_date_index_monotonic()
        roll_calendar.check_dates_are_valid_for_prices(dict_of_final_prices)

        if not quiet:
            print(f"  Generated {len(roll_calendar)} roll entries")
            print(f"  First roll: {roll_calendar.index[0]}")
            print(f"  Last roll: {roll_calendar.index[-1]}")

    except Exception as e:
        print(f"  ERROR building roll calendar: {e}")
        return False

    # SAFETY CHECK: Don't replace a calendar with a shorter one
    # This happens when early contract data is sparse and the algorithm can't
    # build a complete calendar (e.g., HEATOIL went from 498 to 3 entries)
    if existing_count > 0 and len(roll_calendar) < existing_count * 0.8:
        if force:
            print(f"  WARNING: New calendar ({len(roll_calendar)} entries) is smaller "
                  f"than existing ({existing_count}). Proceeding with --force.")
        else:
            print(f"  ABORTED: New calendar ({len(roll_calendar)} entries) would be smaller "
                  f"than existing ({existing_count}).")
            print(f"           This usually means sparse early data. Use --force to override.")
            print(f"           Consider using extend_roll_calendars.py instead to safely extend forward.")
            return False

    # Save to CSV
    try:
        csv_roll_calendars.add_roll_calendar(
            instrument_code, roll_calendar, ignore_duplication=True
        )
        if not quiet:
            print(f"  Saved roll calendar to {ROLL_CALENDAR_PATH}/{instrument_code}.csv")
    except Exception as e:
        print(f"  ERROR saving roll calendar: {e}")
        return False

    return True


def rebuild_multiple_prices(instrument_code: str, quiet: bool = False) -> bool:
    """
    Rebuild multiple prices for one instrument.
    """
    if not quiet:
        print("\n  Rebuilding multiple prices...")

    from sysinit.futures.build_multiple_prices import process_single_instrument

    success, result = process_single_instrument(instrument_code)

    if success:
        if not quiet:
            print(f"  Multiple prices: {result} rows")
        return True
    else:
        print(f"  ERROR: {result}")
        return False


def rebuild_adjusted_prices(instrument_code: str, quiet: bool = False) -> bool:
    """
    Rebuild adjusted prices for one instrument.
    """
    if not quiet:
        print("\n  Rebuilding adjusted prices...")

    from sysinit.futures.build_adjusted_prices import process_single_instrument

    success, result = process_single_instrument(instrument_code)

    if success:
        if not quiet:
            print(f"  Adjusted prices: {result} rows")
        return True
    else:
        print(f"  ERROR: {result}")
        return False


def fix_instrument(
    instrument_code: str,
    diag_prices=None,
    quiet: bool = False,
    force: bool = False,
) -> bool:
    """
    Fix one instrument by regenerating roll calendar,
    then rebuilding multiple and adjusted prices.
    """
    # Step 1: Regenerate roll calendar
    if not regenerate_roll_calendar(instrument_code, diag_prices, quiet, force):
        return False

    # Step 2: Rebuild multiple prices
    if not rebuild_multiple_prices(instrument_code, quiet):
        return False

    # Step 3: Rebuild adjusted prices
    if not rebuild_adjusted_prices(instrument_code, quiet):
        return False

    if not quiet:
        print(f"\n  SUCCESS: {instrument_code} is now fixed!")
    return True


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Detect and fix truncated or broken roll calendars"
    )
    parser.add_argument(
        "--detect",
        action="store_true",
        help="Detect truncated roll calendars (dry run)",
    )
    parser.add_argument(
        "--detect-broken",
        action="store_true",
        help="Detect broken roll calendars (missing contracts)",
    )
    parser.add_argument(
        "--fix",
        action="store_true",
        help="Fix truncated roll calendars",
    )
    parser.add_argument(
        "--instruments",
        nargs="+",
        help="Specific instruments to fix (default: all truncated)",
    )
    parser.add_argument(
        "--min-gap-years",
        type=float,
        default=1.0,
        help="Minimum gap in years to consider truncated (default: 1.0)",
    )
    parser.add_argument(
        "--quiet", "-q",
        action="store_true",
        help="Quiet mode - only show errors and summary",
    )
    parser.add_argument(
        "--force", "-f",
        action="store_true",
        help="Force regeneration even if new calendar is smaller (risky)",
    )

    args = parser.parse_args()

    if not args.detect and not args.detect_broken and not args.fix:
        parser.print_help()
        print("\nError: Must specify --detect, --detect-broken, or --fix")
        return 1

    min_gap_days = int(args.min_gap_years * 365)

    if args.detect:
        if not args.quiet:
            print("=" * 60)
            print("DETECTING TRUNCATED ROLL CALENDARS")
            print("=" * 60)
            print(f"Minimum gap: {args.min_gap_years} years\n")

        truncated = detect_truncated_roll_calendars(min_gap_days, quiet=args.quiet)

        if not truncated:
            print("No truncated roll calendars found!")
            return 0

        print(f"Found {len(truncated)} instruments with truncated roll calendars:\n")
        print(f"{'Instrument':20} {'Contracts From':15} {'Roll Cal From':15} {'Gap (years)'}")
        print("-" * 65)
        for t in truncated:
            print(f"{t['instrument']:20} {t['contracts_from']:15} {t['roll_cal_from']:15} {t['gap_years']}")

        print(f"\nTo fix these, run:")
        print(f"  python pst_import/fix_roll_calendars.py --fix")
        return 0

    if args.detect_broken:
        if not args.quiet:
            print("=" * 60)
            print("DETECTING BROKEN ROLL CALENDARS")
            print("=" * 60)

        broken = detect_broken_roll_calendars(quiet=args.quiet)

        if not broken:
            print("No broken roll calendars found!")
            return 0

        print(f"Found {len(broken)} instruments with broken roll calendars:\n")
        print(f"{'Instrument':20} {'Missing':10} {'Total Rolls':12} Missing Contracts")
        print("-" * 70)
        for b in broken:
            missing_str = ", ".join(b["missing_contracts"][:5])
            if len(b["missing_contracts"]) > 5:
                missing_str += f" (+{len(b['missing_contracts']) - 5} more)"
            print(f"{b['instrument']:20} {b['missing_count']:<10} {b['total_rolls']:<12} {missing_str}")

        print(f"\nTo fix these, run:")
        print(f"  python pst_import/fix_roll_calendars.py --fix --instruments <INSTRUMENT>")
        return 0

    if args.fix:
        # Initialize diagPrices once
        diag_prices = get_diag_prices()

        if args.instruments:
            # Validate instruments exist
            contract_prices = diag_prices.db_futures_contract_price_data
            all_instruments = contract_prices.get_list_of_instrument_codes_with_merged_price_data()
            invalid = [i for i in args.instruments if i not in all_instruments]
            if invalid:
                print(f"Error: Unknown instruments: {', '.join(invalid)}")
                return 1

            instruments_to_fix = args.instruments
            if not args.quiet:
                print("=" * 60)
                print("FIXING TRUNCATED ROLL CALENDARS")
                print("=" * 60)
                print(f"Fixing specified instruments: {', '.join(instruments_to_fix)}")
        else:
            if not args.quiet:
                print("=" * 60)
                print("FIXING TRUNCATED ROLL CALENDARS")
                print("=" * 60)
                print("Detecting truncated roll calendars...")

            truncated = detect_truncated_roll_calendars(min_gap_days, diag_prices, args.quiet)
            instruments_to_fix = [t["instrument"] for t in truncated]

            if not args.quiet:
                print(f"Found {len(instruments_to_fix)} instruments to fix")

        if not instruments_to_fix:
            print("No instruments to fix!")
            return 0

        results = {}
        for i, instrument in enumerate(instruments_to_fix, 1):
            if not args.quiet:
                print(f"\n[{i}/{len(instruments_to_fix)}] Processing {instrument}...")
            results[instrument] = fix_instrument(instrument, diag_prices, args.quiet, args.force)

        # Summary
        print("\n" + "=" * 60)
        print("SUMMARY")
        print("=" * 60)

        fixed = [k for k, v in results.items() if v]
        failed = [k for k, v in results.items() if not v]

        if fixed:
            print(f"\nFIXED ({len(fixed)}):")
            for instr in fixed:
                print(f"  {instr}")

        if failed:
            print(f"\nFAILED ({len(failed)}):")
            for instr in failed:
                print(f"  {instr}")

        if not fixed and not failed:
            print("\nNo instruments processed.")

        print(f"\nTotal: {len(fixed)} fixed, {len(failed)} failed")

        return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
