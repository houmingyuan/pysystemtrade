"""
Rebuild a roll calendar from contract prices, with the knobs needed to repair
calendars that cross a change in the underlying contract series.

`fix_roll_calendars.py` regenerates a calendar from every contract we hold, and
`extend_roll_calendars.py` appends forward from the existing (good) history.
Neither copes with two real cases seen in the Norgate import:

* **Sparse early data** - the generator walks contract by contract and gives up
  on the first gap. HEATOIL, for example, produces 3 rows from 1979 and stops,
  because 1978-79 only has a handful of contracts. Dropping contracts before
  1980-01 produces a complete 563 row calendar instead.
* **A change in contract frequency** - NIKKEI-SGX_mini was a quarterly series
  until 2002 and a monthly series from 2003, with January/February/April 2003
  missing entirely. The generator cannot bridge that, so the calendar has to be
  spliced: keep the old history, add an explicit bridging roll, then take the
  generated entries from the point where the chain reconnects.

Usage:
    # dry run, show what would be written
    python sysinit/futures/rebuild_roll_calendar_from_prices.py \
        --instrument HEATOIL --min-contract 198001 --dry-run

    # regenerate HEATOIL from contracts dated 1980-01 onwards
    python sysinit/futures/rebuild_roll_calendar_from_prices.py \
        --instrument HEATOIL --min-contract 198001

    # splice NIKKEI-SGX_mini: keep pre-2003 history, bridge 2003-03, take the rest
    python sysinit/futures/rebuild_roll_calendar_from_prices.py \
        --instrument NIKKEI-SGX_mini --min-contract 200303 \
        --keep-before 2003-01-01 \
        --bridge 2003-03-12,200303,200306,200306

Options:
    --min-contract YYYYMM   drop contracts dated before this month
    --keep-before DATE      keep existing calendar rows before DATE, replace the rest
    --bridge DATE,CUR,NEXT,CARRY
                            insert an explicit roll row (repeatable)
    --no-rebuild            skip rebuilding multiple / adjusted prices
"""

import argparse
import contextlib
import io
import sys

import pandas as pd

from sysobjects.dict_of_futures_per_contract_prices import (
    dictFuturesContractFinalPrices,
)
from sysobjects.roll_calendars import rollCalendar
from sysdata.csv.csv_roll_calendars import csvRollCalendarData
from sysdata.csv.csv_roll_parameters import csvRollParametersData
from sysproduction.data.prices import diagPrices


ROLL_CALENDAR_PATH = "data/futures/roll_calendars_csv"
INDEX_NAME = "current_roll_date"

# rollCalendar.create_from_prices prints every row it considers; keep a lid on it
NOISY_LINE_FILTERS = ("Warning", "Couldn't find", "ERROR")
MAX_NOTABLE_LINES = 5


def notable_lines(captured: str) -> list:
    return [
        line
        for line in captured.splitlines()
        if any(marker in line for marker in NOISY_LINE_FILTERS)
    ]


def contract_code(value: str) -> int:
    """
    Accept either the 6 digit YYYYMM form or the 8 digit YYYYMM00 form used in
    the roll calendar files.
    """
    text = str(value).strip()
    if len(text) == 6:
        text = text + "00"
    if len(text) != 8 or not text.isdigit():
        raise Exception(f"Bad contract code {value!r}, expected YYYYMM or YYYYMM00")
    return int(text)


def generate_from_prices(diag_prices, instrument_code: str, min_contract: str):
    """
    Build a calendar from contracts dated min_contract or later.
    """
    roll_parameters = csvRollParametersData().get_roll_parameters(instrument_code)

    dict_of_prices = diag_prices.db_futures_contract_price_data.get_merged_prices_for_instrument(
        instrument_code
    )
    final_prices = dict_of_prices.final_prices()
    threshold = str(min_contract).strip()[:6]
    filtered = {
        contract: prices
        for contract, prices in final_prices.items()
        if len(prices) > 0 and str(contract)[:6] >= threshold
    }

    if not filtered:
        raise Exception(
            f"No contracts at or after {threshold} for {instrument_code}"
        )

    captured = io.StringIO()
    with contextlib.redirect_stdout(captured):
        calendar = rollCalendar.create_from_prices(
            dictFuturesContractFinalPrices(filtered), roll_parameters
        )

    lines = notable_lines(captured.getvalue())
    for line in lines[:MAX_NOTABLE_LINES]:
        print(f"  [generator] {line}")
    if len(lines) > MAX_NOTABLE_LINES:
        print(f"  [generator] ... and {len(lines) - MAX_NOTABLE_LINES} more warnings")

    return calendar


def load_existing(roll_calendar_data, instrument_code: str) -> pd.DataFrame:
    try:
        existing = roll_calendar_data.get_roll_calendar(instrument_code)
    except Exception:
        return pd.DataFrame()

    if len(existing) == 0:
        return pd.DataFrame()

    return pd.DataFrame(existing).rename_axis(INDEX_NAME)


def rows_before(existing: pd.DataFrame, keep_before) -> list:
    """
    Split existing rows into (kept, dropped) around the keep_before date.
    """
    if len(existing) == 0 or keep_before is None:
        return [], []

    cut = pd.Timestamp(keep_before)
    rows = list(existing.iterrows())
    kept = [row for row in rows if row[0] < cut]
    dropped = [row for row in rows if row[0] >= cut]

    return kept, dropped


def bridge_rows(bridge_args) -> list:
    """
    Parse --bridge DATE,CURRENT,NEXT,CARRY into calendar rows.
    """
    rows = []
    for spec in bridge_args or []:
        parts = [piece.strip() for piece in spec.split(",")]
        if len(parts) != 4:
            raise Exception(f"Bad --bridge value {spec!r}, expected DATE,CUR,NEXT,CARRY")
        date_str, current, next_contract, carry = parts
        rows.append(
            (
                pd.Timestamp(date_str),
                {
                    "current_contract": contract_code(current),
                    "next_contract": contract_code(next_contract),
                    "carry_contract": contract_code(carry),
                },
            )
        )

    return sorted(rows, key=lambda row: row[0])


def trim_to_chain(generated: pd.DataFrame, previous_next_contract: int) -> pd.DataFrame:
    """
    Drop leading generated rows until the contract chain reconnects with
    previous_next_contract, then insist the rest of the chain is continuous.
    """
    rows = []
    expected = previous_next_contract
    connected = False

    for date, row in generated.iterrows():
        current = int(row["current_contract"])
        next_contract = int(row["next_contract"])

        if not connected:
            if current != expected:
                continue
            connected = True
        elif current != expected:
            raise Exception(
                f"Broken chain at {date}: expected current_contract {expected}, "
                f"got {current}"
            )

        rows.append((date, dict(row)))
        expected = next_contract

    if not rows:
        raise Exception(
            f"Generated entries never connect to current contract {previous_next_contract}"
        )

    return pd.DataFrame.from_dict(dict(rows), orient="index").rename_axis(INDEX_NAME)


def assemble(existing, generated, keep_before, bridges, instrument_code: str):
    """
    Combine kept history, explicit bridge rows and generated entries, dropping
    generated rows up to the point where the contract chain reconnects.
    """
    kept, dropped = rows_before(existing, keep_before)
    bridge = bridge_rows(bridges)

    rows = list(kept) + bridge

    if not rows:
        return generated

    if dropped and not bridge:
        raise Exception(
            f"{instrument_code}: {len(dropped)} existing rows would be dropped and "
            "no --bridge row was given to keep the contract chain continuous"
        )

    previous_next_contract = int(rows[-1][1]["next_contract"])
    tail = trim_to_chain(generated, previous_next_contract)

    combined = pd.concat([pd.DataFrame.from_dict(dict(rows), orient="index"), tail])
    combined = combined.sort_index()
    combined = combined[~combined.index.duplicated(keep="first")]

    return rollCalendar(combined.rename_axis(INDEX_NAME))


def rebuild_prices(instrument_code: str) -> None:
    from sysinit.futures.build_adjusted_prices import (
        process_single_instrument as build_adjusted,
    )
    from sysinit.futures.build_multiple_prices import (
        process_single_instrument as build_multiple,
    )

    for label, build in (("multiple", build_multiple), ("adjusted", build_adjusted)):
        success, result = build(instrument_code)
        if not success:
            raise Exception(f"Rebuilding {label} prices failed: {result}")
        print(f"    {label} prices: {result} rows")


def process_instrument(args, diag_prices) -> bool:
    instrument_code = args.instrument
    print(f"\n{'=' * 60}")
    print(f"REBUILDING ROLL CALENDAR: {instrument_code}")
    print("=" * 60)

    roll_calendar_data = csvRollCalendarData(ROLL_CALENDAR_PATH)
    existing = load_existing(roll_calendar_data, instrument_code)
    print(f"  Existing calendar: {len(existing)} rows")

    generated = generate_from_prices(diag_prices, instrument_code, args.min_contract)
    print(
        f"  Generated from contracts >= {args.min_contract}: {len(generated)} rows "
        f"({generated.index[0].date()} -> {generated.index[-1].date()})"
    )

    final = assemble(
        existing, generated, args.keep_before, args.bridge, instrument_code
    )

    final.check_if_date_index_monotonic()
    print(
        f"  Final calendar: {len(final)} rows "
        f"({final.index[0].date()} -> {final.index[-1].date()})"
    )

    if args.dry_run:
        print("  dry run: nothing written")
        print(final.head(3).to_string())
        print("  ...")
        print(final.tail(3).to_string())
        return True

    roll_calendar_data.add_roll_calendar(
        instrument_code, final, ignore_duplication=True
    )
    print(f"  Saved to {ROLL_CALENDAR_PATH}/{instrument_code}.csv")

    if args.rebuild:
        rebuild_prices(instrument_code)

    return True


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        description="Rebuild a roll calendar from contract prices"
    )
    parser.add_argument("--instrument", "-i", required=True)
    parser.add_argument("--min-contract", required=True, help="YYYYMM")
    parser.add_argument("--keep-before", default=None, help="YYYY-MM-DD")
    parser.add_argument(
        "--bridge",
        action="append",
        help="DATE,CURRENT,NEXT,CARRY (repeatable)",
    )
    parser.add_argument(
        "--no-rebuild",
        dest="rebuild",
        action="store_false",
        help="skip rebuilding multiple / adjusted prices",
    )
    parser.add_argument("--dry-run", action="store_true")
    parser.set_defaults(rebuild=True)
    args = parser.parse_args(argv)

    diag_prices = diagPrices()
    process_instrument(args, diag_prices)

    return 0


if __name__ == "__main__":
    sys.exit(main())
