"""
端到端验证单个品种的数据流是否可用（只读，不写任何数据）。

链路：
    合约价格(parquet) -> 换月日历(CSV) -> multiple prices(parquet) -> adjusted prices(parquet)

校验内容：
    1. 合约价格：合约数量、日期范围、近期合约是否都有数据
    2. 换月日历：末端日期、日历给出的前端合约、该前端合约是否真的还有价格
    3. multiple prices：最新日期、落后天数、PRICE 是否为空、前端合约是否与日历一致
    4. adjusted prices：最新日期、是否停滞（连续相同收盘价）
    5. 交叉验证：近期成交量最大的合约是否就是换月日历的前端合约

用法：
    python pst_import/verify_instrument_dataflow.py
    python pst_import/verify_instrument_dataflow.py --instrument VIX --instrument VIX_mini
    python pst_import/verify_instrument_dataflow.py --instrument VIX --json
"""
import argparse
import glob
import json
import os

import pandas as pd

from syscore.fileutils import get_resolved_pathname
from sysdata.csv.csv_roll_calendars import csvRollCalendarData

ROLL_CALENDAR_PATH = "data/futures/roll_calendars_csv"
DEFAULT_INSTRUMENTS = ["VIX", "VIX_mini"]

# 前端合约价格陈旧超过这个天数就认为数据流断了
MAX_FRONT_STALE_DAYS = 4
# multiple prices / adjusted prices 落后上一环超过这个天数就报警
MAX_LAG_DAYS = 1


def parquet_root() -> str:
    from sysdata.config.production_config import get_production_config

    return get_resolved_pathname(get_production_config().get_element("parquet_store"))


def contract_str(value) -> str:
    """换月日历读进来是整数，合约价格文件名是字符串，统一成 'YYYMM00'。"""
    if isinstance(value, str):
        return value
    try:
        return f"{int(value):08d}"
    except (TypeError, ValueError):
        return str(value)


def load_contract_prices(directory: str, instrument_code: str) -> dict:
    """读取 {instrument}#{contract}.parquet，返回 {contract_str: DataFrame}。"""
    out = {}
    for path in sorted(glob.glob(f"{directory}/{instrument_code}#*.parquet")):
        contract_str = os.path.basename(path).split("#")[1][: -len(".parquet")]
        prices = pd.read_parquet(path)
        prices.index = pd.DatetimeIndex(prices.index)
        out[contract_str] = prices
    return out


def daily_final_and_volume(prices: pd.DataFrame) -> pd.DataFrame:
    """把日内数据压成日线（当日最后一条价格 + 当日成交量合计）。"""
    if prices is None or len(prices) == 0:
        return pd.DataFrame(columns=["FINAL", "VOLUME"])
    by_day = pd.DatetimeIndex(prices.index).normalize()
    final = prices["FINAL"].groupby(by_day).last()
    volume = pd.to_numeric(prices["VOLUME"], errors="coerce").groupby(by_day).sum()
    return pd.DataFrame({"FINAL": final, "VOLUME": volume}).dropna(how="all")


def check_contract_prices(instrument_code: str, contract_prices: dict) -> dict:
    result = {"instrument": instrument_code, "issues": []}
    if not contract_prices:
        result["status"] = "FAIL"
        result["issues"].append(f"没有任何合约价格文件（{instrument_code}#*.parquet）")
        return result

    daily = {c: daily_final_and_volume(p) for c, p in contract_prices.items()}
    daily = {c: d for c, d in daily.items() if len(d)}
    last_dates = {c: d.index.max() for c, d in daily.items()}
    last_date = max(last_dates.values())
    near = [
        c
        for c, d in daily.items()
        if d.index.max() >= last_date - pd.Timedelta(days=60)
    ]

    result.update(
        {
            "contracts_with_files": len(contract_prices),
            "data_start": str(min(d.index.min() for d in daily.values()).date()),
            "data_end": str(last_date.date()),
            "near_contract_last_date": {
                c: str(last_dates[c].date()) for c in sorted(near)
            },
        }
    )

    # 只有“还有成交量但价格停更”的合约才算异常（正常到期合约停更是预期行为）
    stale = {}
    for contract in near:
        daily_contract = daily[contract]
        if last_dates[contract] >= last_date - pd.Timedelta(days=3):
            continue
        recent_volume = daily_contract[daily_contract.index >= last_date - pd.Timedelta(days=7)][
            "VOLUME"
        ].sum()
        if recent_volume > 0:
            stale[contract] = str(last_dates[contract].date())
    if stale:
        result["issues"].append(f"近一周仍有成交量但价格停更的合约：{stale}")
    result["status"] = "WARN" if stale else "OK"
    return result


def check_roll_calendar(instrument_code: str, contract_prices: dict) -> dict:
    result = {"issues": []}
    try:
        calendar = csvRollCalendarData(ROLL_CALENDAR_PATH).get_roll_calendar(
            instrument_code
        )
    except Exception as e:
        result["status"] = "FAIL"
        result["issues"].append(f"读不到换月日历：{e}")
        return result

    index = pd.DatetimeIndex(calendar.index)
    front_by_date = {}
    current = None
    for ts, row in calendar.iterrows():
        current = contract_str(
            row["current_contract"] if current is None else row["next_contract"]
        )
        front_by_date[pd.Timestamp(ts).normalize()] = current

    last_row = calendar.iloc[-1]
    result.update(
        {
            "roll_calendar_rows": len(calendar),
            "roll_calendar_start": str(pd.Timestamp(index.min()).date()),
            "roll_calendar_end": str(pd.Timestamp(index.max()).date()),
            "front_contract_at_end": contract_str(last_row["next_contract"]),
        }
    )

    front = contract_str(last_row["next_contract"])
    daily = daily_final_and_volume(contract_prices.get(front))
    latest_contract_date = max(
        daily_final_and_volume(p).index.max()
        for p in contract_prices.values()
        if len(daily_final_and_volume(p))
    )
    if len(daily) == 0:
        result["issues"].append(f"日历前端合约 {front} 完全没有价格数据")
        result["status"] = "FAIL"
    else:
        front_last = daily.index.max()
        days_stale = (latest_contract_date.normalize() - front_last.normalize()).days
        result["front_contract_last_price"] = str(front_last.date())
        result["front_contract_stale_days"] = days_stale
        if days_stale > MAX_FRONT_STALE_DAYS:
            result["issues"].append(
                f"日历前端合约 {front} 最后价格 {front_last.date()}，比最新合约价格落后 {days_stale} 天"
            )
            result["status"] = "FAIL"
        else:
            result["status"] = "OK"

    result["_front_by_date"] = front_by_date
    return result


def check_multiple_prices(
    instrument_code: str, root: str, roll_info: dict, contract_prices: dict
) -> dict:
    result = {"issues": []}
    path = f"{root}/futures_multiple_prices/{instrument_code}.parquet"
    if not os.path.exists(path):
        result["status"] = "FAIL"
        result["issues"].append(f"没有 multiple prices 文件：{path}")
        return result

    multiple = pd.read_parquet(path)
    multiple.index = pd.DatetimeIndex(multiple.index)
    last_date = multiple.index.max()
    result["multiple_prices_end"] = str(last_date.date())
    result["multiple_prices_rows"] = len(multiple)

    recent = multiple.tail(10)
    null_price = recent[recent["PRICE"].isnull()]
    result["recent_price_nulls"] = len(null_price)
    result["recent_front_contract"] = contract_str(recent["PRICE_CONTRACT"].iloc[-1])
    result["recent_rows"] = [
        {
            "date": str(pd.Timestamp(ts).date()),
            "PRICE": None if pd.isna(row["PRICE"]) else float(row["PRICE"]),
            "PRICE_CONTRACT": contract_str(row["PRICE_CONTRACT"]),
            "FORWARD_CONTRACT": contract_str(row["FORWARD_CONTRACT"]),
        }
        for ts, row in recent.iterrows()
    ]

    if len(null_price):
        result["issues"].append(
            f"最近 10 行里有 {len(null_price)} 行 PRICE 为空（{null_price.index.min().date()} 起），"
            "策略据此算收益会得到 0/缺失价格"
        )
        result["status"] = "FAIL"

    dated = [
        d.index.max()
        for d in (daily_final_and_volume(p) for p in contract_prices.values())
        if len(d)
    ]
    if dated:
        contract_last = max(dated)
        lag = (contract_last.normalize() - last_date.normalize()).days
        result["lag_vs_contract_prices_days"] = lag
        if lag > MAX_LAG_DAYS:
            result["issues"].append(
                f"multiple prices 落后合约价格 {lag} 天（合约价格到 {contract_last.date()}）"
            )
            result["status"] = result.get("status", "WARN")

    front_by_date = roll_info.get("_front_by_date", {})
    mismatches = []
    for ts, row in recent.iterrows():
        expected = front_by_date.get(pd.Timestamp(ts).normalize())
        if expected is None:
            continue
        if contract_str(row["PRICE_CONTRACT"]) != contract_str(expected):
            mismatches.append(
                {
                    "date": str(pd.Timestamp(ts).date()),
                    "multiple": contract_str(row["PRICE_CONTRACT"]),
                    "calendar": expected,
                }
            )
    if mismatches:
        result["roll_mismatches"] = mismatches
        result["issues"].append(
            f"multiple prices 前端合约与换月日历不一致（最近 10 行中 {len(mismatches)} 行）"
        )
        result["status"] = "FAIL"

    result.setdefault("status", "OK")
    return result


def check_adjusted_prices(instrument_code: str, root: str, multiple_info: dict) -> dict:
    result = {"issues": []}
    path = f"{root}/futures_adjusted_prices/{instrument_code}.parquet"
    if not os.path.exists(path):
        result["status"] = "FAIL"
        result["issues"].append(f"没有 adjusted prices 文件：{path}")
        return result

    adjusted = pd.read_parquet(path)["price"]
    adjusted.index = pd.DatetimeIndex(adjusted.index)
    last_date = adjusted.index.max()
    result["adjusted_prices_end"] = str(last_date.date())

    tail = adjusted.tail(10)
    unchanged_tail = int((tail.diff() == 0).sum())
    changed = adjusted[adjusted.diff() != 0]
    last_change = changed.index.max() if len(changed) else None
    result["last_price_change"] = (
        str(pd.Timestamp(last_change).date()) if last_change is not None else None
    )
    result["unchanged_in_last_10"] = unchanged_tail
    result["last_10_values"] = [
        {"date": str(pd.Timestamp(ts).date()), "price": float(v)}
        for ts, v in tail.items()
    ]

    mp_end = multiple_info.get("multiple_prices_end")
    if mp_end:
        lag = (pd.Timestamp(mp_end) - last_date.normalize()).days
        result["lag_vs_multiple_prices_days"] = lag
        if lag > MAX_LAG_DAYS:
            result["issues"].append(f"adjusted prices 落后 multiple prices {lag} 天")
            result["status"] = "FAIL"

    if unchanged_tail >= 3:
        result["issues"].append(
            f"最近 10 天里有 {unchanged_tail} 天收盘价完全没变化，最后一个变化日 {result['last_price_change']}"
        )
        result["status"] = "FAIL"

    result.setdefault("status", "OK")
    return result


def check_liquid_contract(contract_prices: dict, roll_info: dict) -> dict:
    """近期成交量最大的合约（=真正的前端合约）是否与换月日历末端一致。"""
    result = {"issues": []}
    daily = {c: daily_final_and_volume(p) for c, p in contract_prices.items()}
    daily = {c: d for c, d in daily.items() if len(d)}
    if not daily:
        result["status"] = "SKIP"
        return result

    cutoff = max(d.index.max() for d in daily.values()) - pd.Timedelta(days=7)
    window = [
        (c, float(d[d.index >= cutoff]["VOLUME"].sum()))
        for c, d in daily.items()
        if d.index.max() >= cutoff
    ]
    window = [kv for kv in window if kv[1] > 0]
    if not window:
        result["status"] = "SKIP"
        return result

    window = sorted(window, key=lambda kv: (-kv[1], kv[0]))[:5]
    result["volume_leaders"] = [{"contract": c, "volume": v} for c, v in window]
    liquid = window[0][0]
    calendar_front = roll_info.get("front_contract_at_end")
    result["liquid_contract"] = liquid
    result["roll_calendar_front"] = calendar_front
    if str(liquid) != str(calendar_front):
        result["issues"].append(
            f"近一周成交量第一是 {liquid}，换月日历末端前端却是 {calendar_front}"
        )
        result["status"] = "WARN"
    else:
        result["status"] = "OK"
    return result


def verify_instrument(instrument_code: str, root: str) -> dict:
    contract_prices = load_contract_prices(
        f"{root}/futures_contract_prices", instrument_code
    )
    contracts = check_contract_prices(instrument_code, contract_prices)
    roll = check_roll_calendar(instrument_code, contract_prices)
    multiple = check_multiple_prices(instrument_code, root, roll, contract_prices)
    adjusted = check_adjusted_prices(instrument_code, root, multiple)
    liquid = check_liquid_contract(contract_prices, roll)

    roll.pop("_front_by_date", None)

    statuses = [
        contracts["status"],
        roll["status"],
        multiple["status"],
        adjusted["status"],
    ]
    overall = (
        "FAIL" if "FAIL" in statuses else ("WARN" if "WARN" in statuses else "OK")
    )
    return {
        "instrument": instrument_code,
        "status": overall,
        "contract_prices": contracts,
        "roll_calendar": roll,
        "multiple_prices": multiple,
        "adjusted_prices": adjusted,
        "liquid_contract": liquid,
    }


def print_report(report: dict) -> None:
    print("=" * 78)
    print(f"{report['instrument']} 数据流校验：{report['status']}")
    print("=" * 78)

    cp = report["contract_prices"]
    print(f"[1] 合约价格        {cp['status']}")
    if "contracts_with_files" in cp:
        print(
            f"    合约文件 {cp['contracts_with_files']} 个，覆盖 {cp['data_start']} ~ {cp['data_end']}"
        )
        print(f"    近期合约最新价格日：{cp['near_contract_last_date']}")

    roll = report["roll_calendar"]
    print(f"[2] 换月日历        {roll['status']}")
    if "roll_calendar_rows" in roll:
        print(
            f"    {roll['roll_calendar_rows']} 行，覆盖 {roll['roll_calendar_start']} ~ "
            f"{roll['roll_calendar_end']}，末端前端合约 {roll['front_contract_at_end']}"
        )
        print(
            f"    该前端合约最后价格 {roll.get('front_contract_last_price')}"
            f"（陈旧 {roll.get('front_contract_stale_days')} 天）"
        )

    mp = report["multiple_prices"]
    print(f"[3] multiple prices {mp['status']}")
    if "multiple_prices_end" in mp:
        print(
            f"    最新 {mp['multiple_prices_end']}，{mp['multiple_prices_rows']} 行，"
            f"当前前端合约 {mp['recent_front_contract']}，"
            f"落后合约价格 {mp.get('lag_vs_contract_prices_days')} 天"
        )
        print(f"    最近 10 行 PRICE 为空 {mp['recent_price_nulls']} 行")
        for row in mp["recent_rows"][-5:]:
            print(
                f"      {row['date']}  PRICE={row['PRICE']}  "
                f"PRICE_CONTRACT={row['PRICE_CONTRACT']}  "
                f"FORWARD_CONTRACT={row['FORWARD_CONTRACT']}"
            )
        for m in mp.get("roll_mismatches", [])[:6]:
            print(
                f"      ! 与日历不一致 {m['date']}：multiple={m['multiple']} "
                f"calendar={m['calendar']}"
            )

    ap = report["adjusted_prices"]
    print(f"[4] adjusted prices {ap['status']}")
    if "adjusted_prices_end" in ap:
        print(
            f"    最新 {ap['adjusted_prices_end']}，最后一个变化日 {ap['last_price_change']}，"
            f"最近 10 行未变化 {ap['unchanged_in_last_10']} 行"
        )

    liq = report["liquid_contract"]
    print(f"[5] 成交量第一合约  {liq['status']}")
    if liq.get("volume_leaders"):
        print(f"    近一周成交量前 5：{liq['volume_leaders']}")
        print(
            f"    成交量第一 {liq.get('liquid_contract')} vs "
            f"日历前端 {liq.get('roll_calendar_front')}"
        )

    issues = []
    for name, section in (
        ("合约价格", cp),
        ("换月日历", roll),
        ("multiple prices", mp),
        ("adjusted prices", ap),
        ("成交量第一合约", liq),
    ):
        for issue in section.get("issues", []):
            issues.append(f"  - [{name}] {issue}")
    print("-" * 78)
    if issues:
        print("发现的问题：")
        print("\n".join(issues))
    else:
        print("没有发现问题。")
    print()


def main():
    parser = argparse.ArgumentParser(description="验证品种数据流（只读）")
    parser.add_argument(
        "--instrument",
        action="append",
        dest="instruments",
        help="品种代码，可重复；默认 VIX 与 VIX_mini",
    )
    parser.add_argument("--json", action="store_true", help="输出 JSON")
    args = parser.parse_args()

    instruments = args.instruments or DEFAULT_INSTRUMENTS
    root = parquet_root()

    reports = [verify_instrument(code, root) for code in instruments]
    if args.json:
        print(json.dumps(reports, ensure_ascii=False, indent=2, default=str))
    else:
        print(f"\nparquet 价格库：{root}\n")
        for report in reports:
            print_report(report)

    failed = [r["instrument"] for r in reports if r["status"] == "FAIL"]
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
