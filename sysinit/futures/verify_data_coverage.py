"""
Verify data coverage for all imported instruments.

Checks:
1. Contract prices exist
2. Roll calendar covers contract range (within tolerance)
3. Adjusted prices exist and are current
4. No major gaps in adjusted price series

Usage:
    python sysinit/futures/verify_data_coverage.py
    python sysinit/futures/verify_data_coverage.py --instrument EUR
    python sysinit/futures/verify_data_coverage.py --summary
    python sysinit/futures/verify_data_coverage.py --gaps-only
"""

import argparse
from datetime import datetime
from dataclasses import dataclass
from pathlib import Path

import pandas as pd

from sysdata.csv.csv_roll_calendars import csvRollCalendarData
from sysproduction.data.prices import diagPrices


# Default paths - adjust for your PST installation
ROLL_CAL_DIR = "data/futures/roll_calendars_csv"

# How many days behind "today" is acceptable for adjusted prices
ACCEPTABLE_LAG_DAYS = 30

# How many years gap at start of roll calendar is acceptable
# (Early futures data is often sparse, so some gap is normal)
ACCEPTABLE_START_GAP_YEARS = 3


@dataclass
class CoverageResult:
    instrument: str
    status: str  # "OK", "GAP", "ERROR"
    contract_start: str
    contract_end: str
    adj_start: str
    adj_end: str
    roll_cal_start: str
    roll_cal_end: str
    gap_days: int  # Days between adj_end and contract_end
    issues: list


def format_timestamp(value) -> str:
    """
    Format a timestamp for display, tolerating None and NaT.

    NaT is truthy, so a plain ``if value`` guard still lets .strftime()
    raise on empty price series.
    """
    if value is None:
        return ""
    if pd.isna(value):
        return ""
    if hasattr(value, "strftime"):
        return value.strftime("%Y-%m-%d")
    return str(value)


def check_instrument_coverage(
    instrument: str,
    diag_prices=None,
    roll_cal_data=None,
) -> CoverageResult:
    """Check data coverage for one instrument."""
    if diag_prices is None:
        diag_prices = diagPrices()
    if roll_cal_data is None:
        roll_cal_data = csvRollCalendarData(ROLL_CAL_DIR)

    issues = []

    # 1. Contract prices
    try:
        contract_prices = diag_prices.db_futures_contract_price_data
        dict_of_prices = contract_prices.get_merged_prices_for_instrument(instrument)

        if len(dict_of_prices) == 0:
            return CoverageResult(
                instrument=instrument, status="ERROR",
                contract_start="", contract_end="", adj_start="", adj_end="",
                roll_cal_start="", roll_cal_end="", gap_days=0,
                issues=["No contract price data"]
            )

        contracts = sorted(dict_of_prices.keys())
        # Get actual date range from price data
        # Use all contracts rather than just the first/last, since either can
        # be an empty (or partially populated) series.
        contract_starts = [
            prices.index.min()
            for prices in dict_of_prices.values()
            if len(prices) > 0
        ]
        contract_ends = [
            prices.index.max()
            for prices in dict_of_prices.values()
            if len(prices) > 0
        ]

        if not contract_starts:
            return CoverageResult(
                instrument=instrument, status="ERROR",
                contract_start="", contract_end="", adj_start="", adj_end="",
                roll_cal_start="", roll_cal_end="", gap_days=0,
                issues=["No contract price rows"]
            )

        contract_start = min(contract_starts)
        contract_end = max(contract_ends)

    except Exception as e:
        return CoverageResult(
            instrument=instrument, status="ERROR",
            contract_start="", contract_end="", adj_start="", adj_end="",
            roll_cal_start="", roll_cal_end="", gap_days=0,
            issues=[f"Contract price error: {e}"]
        )

    # 2. Roll calendar
    try:
        roll_cal = roll_cal_data.get_roll_calendar(instrument)
        roll_cal_start = roll_cal.index.min()
        roll_cal_end = roll_cal.index.max()

        # Check if roll calendar starts much later than contract data
        if pd.notna(roll_cal_start) and pd.notna(contract_start):
            gap_years = (roll_cal_start - contract_start).days / 365
            if gap_years > ACCEPTABLE_START_GAP_YEARS:
                issues.append(
                    f"Roll calendar starts {gap_years:.1f} years after contracts"
                )

    except Exception as e:
        roll_cal_start = None
        roll_cal_end = None
        issues.append(f"Roll calendar error: {e}")

    # 3. Adjusted prices
    try:
        adj_prices = diag_prices.db_futures_adjusted_prices_data
        adj_df = adj_prices.get_adjusted_prices(instrument)

        if len(adj_df) == 0:
            adj_start = None
            adj_end = None
            gap_days = -1
            issues.append("No adjusted prices")
        else:
            adj_start = adj_df.index.min()
            adj_end = adj_df.index.max()

            # Check if adjusted prices are reasonably current
            gap_days = (contract_end - adj_end).days
            if pd.isna(gap_days):
                gap_days = -1
                issues.append("Adjusted prices have no usable end date")
            if gap_days > ACCEPTABLE_LAG_DAYS:
                issues.append(f"Adjusted prices {gap_days} days behind contract data")

    except Exception as e:
        adj_start = None
        adj_end = None
        gap_days = -1
        issues.append(f"Adjusted prices error: {e}")

    # Determine overall status
    if not issues:
        status = "OK"
    elif any("behind" in i for i in issues):
        status = "GAP"  # Critical - missing recent data
    elif any("error" in i.lower() for i in issues):
        status = "ERROR"
    else:
        status = "GAP"  # Historical gap

    return CoverageResult(
        instrument=instrument,
        status=status,
        contract_start=format_timestamp(contract_start),
        contract_end=format_timestamp(contract_end),
        adj_start=format_timestamp(adj_start),
        adj_end=format_timestamp(adj_end),
        roll_cal_start=format_timestamp(roll_cal_start),
        roll_cal_end=format_timestamp(roll_cal_end),
        gap_days=gap_days if gap_days and not pd.isna(gap_days) else 0,
        issues=issues
    )


def get_all_instruments(diag_prices=None) -> list:
    """Get list of all instruments with contract prices."""
    if diag_prices is None:
        diag_prices = diagPrices()

    contract_prices = diag_prices.db_futures_contract_price_data
    return sorted(contract_prices.get_list_of_instrument_codes_with_merged_price_data())


def main():
    parser = argparse.ArgumentParser(description="Verify data coverage for all instruments")
    parser.add_argument("--instrument", "-i", help="Check specific instrument only")
    parser.add_argument("--summary", "-s", action="store_true", help="Summary only")
    parser.add_argument("--gaps-only", "-g", action="store_true", help="Show only instruments with gaps")
    args = parser.parse_args()

    diag_prices = diagPrices()
    roll_cal_data = csvRollCalendarData(ROLL_CAL_DIR)

    if args.instrument:
        instruments = [args.instrument]
    else:
        instruments = get_all_instruments(diag_prices)

    print("=" * 80)
    print("DATA COVERAGE VERIFICATION")
    print("=" * 80)
    print(f"Checking {len(instruments)} instruments...\n")

    results = []
    for inst in instruments:
        result = check_instrument_coverage(inst, diag_prices, roll_cal_data)
        results.append(result)

    # Summary
    ok_count = sum(1 for r in results if r.status == "OK")
    gap_count = sum(1 for r in results if r.status == "GAP")
    error_count = sum(1 for r in results if r.status == "ERROR")

    if args.summary:
        print(f"OK:    {ok_count:3d} instruments (100% coverage)")
        print(f"GAP:   {gap_count:3d} instruments (missing data)")
        print(f"ERROR: {error_count:3d} instruments (critical issues)")
        print(f"\nTotal: {len(results)} instruments")

        if gap_count > 0 or error_count > 0:
            print("\nRun without --summary to see details.")
            print("Run with --gaps-only to see only problem instruments.")
        return

    # Detailed output
    if args.gaps_only:
        results = [r for r in results if r.status != "OK"]

    print(f"{'Instrument':<18} {'Status':<6} {'Adj Start':<12} {'Adj End':<12} {'Gap':>6} Issues")
    print("-" * 90)

    for r in results:
        issue_str = "; ".join(r.issues[:2]) if r.issues else ""
        if len(issue_str) > 35:
            issue_str = issue_str[:32] + "..."
        print(f"{r.instrument:<18} {r.status:<6} {r.adj_start:<12} {r.adj_end:<12} {r.gap_days:>6} {issue_str}")

    print("\n" + "=" * 80)
    print(f"SUMMARY: {ok_count} OK, {gap_count} GAP, {error_count} ERROR")
    print("=" * 80)

    if gap_count > 0 or error_count > 0:
        print("\nTo fix gaps, try:")
        print("  python sysinit/futures/fix_roll_calendars.py --fix")


if __name__ == "__main__":
    main()
