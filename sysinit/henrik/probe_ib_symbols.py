"""
只读探测：给若干候选符号，用 IB 的 reqMatchingSymbols 找出可交易的期货合约，
用于修正 `sysbrokers/IB/config/ib_config_futures.csv` 的符号映射。

用法：
    python sysinit/henrik/probe_ib_symbols.py --queries SXF TSX XT YT IR WH WHT AWH SGXNKM NKM
"""

import argparse
import sys

from ib_async import IB, Future


def probe(ib: IB, query: str) -> None:
    print("\n=== 查询 %s" % query)
    try:
        results = ib.reqMatchingSymbols(query)
    except Exception as error:
        print("  失败: %s: %s" % (type(error).__name__, str(error)[:80]))
        return

    futures = [item for item in results if item.contract.secType == "FUT"]
    if not futures:
        print("  没有期货合约；其它匹配：")
        for item in results[:5]:
            contract = item.contract
            print(
                "    %s %s %s %s"
                % (contract.symbol, contract.secType, contract.primaryExchange, contract.currency)
            )
        return

    for item in futures[:8]:
        contract = item.contract
        print(
            "  期货 symbol=%-8s localSymbol=%-10s exchange=%-10s primaryExch=%-8s ccy=%s "
            "mult=%s expiry=%s desc=%s"
            % (
                contract.symbol,
                contract.localSymbol,
                contract.exchange,
                contract.primaryExchange,
                contract.currency,
                contract.multiplier,
                contract.lastTradeDateOrContractMonth,
                (item.derivativeSecTypes or "")[:40],
            )
        )


def probe_contract(ib: IB, spec: str) -> None:
    """spec 形如 SYMBOL:EXCHANGE:CURRENCY:EXPIRY，直接查合约明细。"""
    parts = spec.split(":")
    while len(parts) < 4:
        parts.append("")
    symbol, exchange, currency, expiry = parts[:4]
    print("\n=== 合约 %s" % spec)
    try:
        details = ib.reqContractDetails(
            Future(
                symbol=symbol,
                lastTradeDateOrContractMonth=expiry,
                exchange=exchange,
                currency=currency,
            )
        )
    except Exception as error:
        print("  失败: %s: %s" % (type(error).__name__, str(error)[:80]))
        return

    if not details:
        print("  没有匹配的合约")
        return
    for item in details[:3]:
        contract = item.contract
        print(
            "  symbol=%-8s localSymbol=%-10s exchange=%-8s primaryExch=%-8s ccy=%s mult=%s "
            "expiry=%s tradingClass=%s longName=%s"
            % (
                contract.symbol,
                contract.localSymbol,
                contract.exchange,
                contract.primaryExchange,
                contract.currency,
                contract.multiplier,
                contract.lastTradeDateOrContractMonth,
                contract.tradingClass,
                (item.longName or "")[:40],
            )
        )


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="探测 IB 期货符号")
    parser.add_argument("--queries", nargs="*", default=[])
    parser.add_argument(
        "--contracts",
        nargs="*",
        default=[],
        help="形如 SYMBOL:EXCHANGE:CURRENCY:EXPIRY 的合约，例如 SXF:MX:CAD:202612",
    )
    parser.add_argument("--port", type=int, default=4001)
    parser.add_argument("--client-id", type=int, default=993)
    args = parser.parse_args(argv)

    ib = IB()
    ib.connect("127.0.0.1", args.port, clientId=args.client_id, timeout=20)
    print("已连接 IB %s" % args.port, flush=True)
    try:
        for query in args.queries:
            probe(ib, query)
        for spec in args.contracts:
            probe_contract(ib, spec)
    finally:
        ib.disconnect()

    return 0


if __name__ == "__main__":
    sys.exit(main())
