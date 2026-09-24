"""
Build adjusted prices for ALL instruments, handling errors gracefully.

This is a batch version that continues on errors and reports failures at the end.
"""
from sysproduction.data.prices import diagPrices
from sysobjects.adjusted_prices import futuresAdjustedPrices


diag_prices = diagPrices()


def process_single_instrument(instrument_code):
    """Process one instrument, return True on success, error message on failure."""
    try:
        db_multiple_prices = diag_prices.db_futures_multiple_prices_data
        db_adjusted_prices = diag_prices.db_futures_adjusted_prices_data

        # Check if multiple prices exist
        multiple_prices = db_multiple_prices.get_multiple_prices(instrument_code)
        if len(multiple_prices) == 0:
            return False, "No multiple prices"

        # Calculate adjusted prices by stitching multiple prices
        adjusted_prices = futuresAdjustedPrices.stitch_multiple_prices(
            multiple_prices, forward_fill=True
        )

        if len(adjusted_prices) == 0:
            return False, "Empty adjusted prices"

        # Write to db
        db_adjusted_prices.add_adjusted_prices(
            instrument_code, adjusted_prices, ignore_duplication=True
        )

        return True, len(adjusted_prices)

    except Exception as e:
        return False, str(e)


def process_all_instruments():
    """Process all instruments with multiple prices."""
    db_multiple_prices = diag_prices.db_futures_multiple_prices_data
    instrument_list = db_multiple_prices.get_list_of_instruments()
    instrument_list.sort()

    print(f"Processing {len(instrument_list)} instruments with multiple prices")
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
            print(f"FAILED: {result}")
            failures.append((instrument_code, result))

    print("\n" + "=" * 60)
    print(f"COMPLETE: {len(successes)} success, {len(failures)} failed")

    if failures:
        print("\nFailed instruments:")
        for inst, error in failures:
            error_short = error[:100] + "..." if len(error) > 100 else error
            print(f"  {inst}: {error_short}")

    return successes, failures


if __name__ == "__main__":
    input("This will build adjusted prices for all instruments. Press Enter to continue (Ctrl-C to abort)")
    successes, failures = process_all_instruments()
