#!/usr/bin/env python3
"""
pysystemtrade dashboard load test (FIR-223).

Measures how long the web dashboard takes to load, per endpoint and per tab,
using a real headless browser (Playwright driving the system Chrome). It can
test an already running dashboard, or start and stop its own instance.

Examples
--------
    # against a running dashboard
    python3 dashboard/load_test.py --base-url http://127.0.0.1:5057

    # start the dashboard on a free port, test it, then shut it down
    python3 dashboard/load_test.py --start-server

    # three cycles, also write raw results as json
    python3 dashboard/load_test.py --start-server --repeat 3 --json /tmp/dash.json

    # only some tabs
    python3 dashboard/load_test.py --tabs rolls,costs,risk

Exit status is non-zero if the page never renders its data.
"""

import argparse
import json
import os
import socket
import subprocess
import sys
import time
import urllib.request

# ordered tab id -> endpoint it loads
TAB_ENDPOINTS = {
    "tab_rolls": "rolls",
    "tab_processes": "processes",
    "tab_pandl": "pandl",
    "tab_trades": "trades",
    "tab_reconciliation": "reconcile",
    "tab_strategy": "strategy",
    "tab_risk": "risk",
    "tab_liquidity": "liquidity",
    "tab_costs": "costs",
    "tab_forex": "forex",
}

STATIC_SUFFIXES = (".js", ".css", ".ico", ".png", ".jpg", ".svg", ".map")


def find_free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def wait_for_server(base_url: str, timeout: float = 60.0) -> bool:
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(base_url + "/", timeout=5) as response:
                if response.status == 200:
                    return True
        except Exception:
            time.sleep(0.5)

    return False


def start_server(port: int) -> subprocess.Popen:
    dashboard_dir = os.path.dirname(os.path.abspath(__file__))
    environment = dict(os.environ, DASHBOARD_PORT=str(port))

    return subprocess.Popen(
        [sys.executable, "app.py"],
        cwd=dashboard_dir,
        env=environment,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )


def is_dashboard_endpoint(url: str, base_url: str) -> bool:
    if not url.startswith(base_url):
        return False

    path = url[len(base_url) :].split("?", 1)[0]
    if path in ("", "/"):
        return True
    if path.startswith("/static/"):
        return False

    return not path.endswith(STATIC_SUFFIXES)


def activate_and_time_tab(page, tab_id: str, base_url: str, timeout: float):
    """
    Click a tab, wait for its endpoint response and for the page to go idle.

    Returns (total_seconds, response_seconds): seconds until the tab is fully
    idle, and seconds until its endpoint responded.
    """
    endpoint_url = base_url + "/" + TAB_ENDPOINTS[tab_id]
    start = time.time()

    with page.expect_response(
        lambda response: response.url.rstrip("/") == endpoint_url,
        timeout=timeout * 1000,
    ) as response_info:
        page.click("label[for='%s']" % tab_id)

    response_seconds = time.time() - start
    page.wait_for_function("window.pending_requests === 0", timeout=timeout * 1000)

    return time.time() - start, response_seconds


def run_once(page, base_url: str, tabs: dict, timeout: float) -> dict:
    result = {"page_load": {}, "tabs": {}, "errors": [], "external_requests": []}

    endpoint_arrival = {}
    external_requests = []
    browser_errors = []
    run_start = [None]

    def on_response(response):
        if is_dashboard_endpoint(response.url, base_url):
            if run_start[0] is None:
                return
            path = "/" + response.url[len(base_url) :].lstrip("/")
            endpoint_arrival[path] = round(time.time() - run_start[0], 2)
        elif not response.url.startswith(base_url) and not response.url.startswith(
            "data:"
        ):
            external_requests.append(response.url)

    def on_console(message):
        if message.type == "error":
            browser_errors.append(message.text)

    page.on("response", on_response)
    page.on("console", on_console)
    page.on("pageerror", lambda error: browser_errors.append("pageerror: %s" % error))

    run_start[0] = time.time()
    page.goto(base_url + "/", wait_until="domcontentloaded")
    page.wait_for_selector("#rolls_status tbody tr", timeout=timeout * 1000)
    result["page_load"]["first_data_seconds"] = round(time.time() - run_start[0], 2)

    page.wait_for_function("window.pending_requests === 0", timeout=timeout * 1000)
    result["page_load"]["all_data_seconds"] = round(time.time() - run_start[0], 2)
    result["page_load"]["endpoints"] = dict(endpoint_arrival)

    # Switch off the default tab first so every measured click changes the tab
    # (and therefore fires a request).
    if "tab_strategy" in TAB_ENDPOINTS and "tab_rolls" in tabs:
        activate_and_time_tab(page, "tab_strategy", base_url, timeout)

    for tab_id in tabs:
        total_seconds, response_seconds = activate_and_time_tab(
            page, tab_id, base_url, timeout
        )
        name = tab_id.replace("tab_", "")
        result["tabs"][name] = {
            "total_seconds": round(total_seconds, 2),
            "response_seconds": round(response_seconds, 2),
        }

    result["errors"] = browser_errors
    result["external_requests"] = sorted(set(external_requests))

    return result


def parse_tabs(spec: str) -> dict:
    if spec.strip().lower() in ("all", ""):
        return TAB_ENDPOINTS

    requested = [name.strip().lower() for name in spec.split(",") if name.strip()]
    selected = {}
    for name in requested:
        tab_id = name if name.startswith("tab_") else "tab_" + name
        if tab_id not in TAB_ENDPOINTS:
            raise SystemExit(
                "unknown tab '%s'; choose from: %s"
                % (name, ", ".join(t.replace("tab_", "") for t in TAB_ENDPOINTS))
            )
        selected[tab_id] = TAB_ENDPOINTS[tab_id]

    return selected


def print_report(base_url: str, results: list) -> None:
    print("=" * 70)
    print("pysystemtrade dashboard load test")
    print("base url: %s" % base_url)
    print("=" * 70)

    for index, result in enumerate(results, start=1):
        load = result["page_load"]
        print("\nrun %d" % index)
        print("  time to first data : %6.2f s" % load["first_data_seconds"])
        print("  time to all data   : %6.2f s" % load["all_data_seconds"])

        print("  endpoint response, seconds after page load (slowest first):")
        for path, seconds in sorted(load["endpoints"].items(), key=lambda kv: -kv[1]):
            print("    %-16s %6.2f s" % (path, seconds))

        print("  tabs (response = endpoint came back, total = tab fully idle):")
        for tab, info in result["tabs"].items():
            print(
                "    %-16s response %6.2f s   total %6.2f s"
                % (tab, info["response_seconds"], info["total_seconds"])
            )

        if result["external_requests"]:
            print("  WARNING: requests to external hosts (should be none):")
            for url in result["external_requests"]:
                print("    %s" % url)

        if result["errors"]:
            print("  browser errors:")
            for error in result["errors"]:
                print("    %s" % error)


def main() -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--base-url", default=None, help="dashboard url to test")
    parser.add_argument(
        "--start-server",
        action="store_true",
        help="start a dashboard on a free port and stop it afterwards",
    )
    parser.add_argument(
        "--repeat", type=int, default=1, help="number of cycles (default 1)"
    )
    parser.add_argument("--tabs", default="all", help="comma separated tabs, or 'all'")
    parser.add_argument(
        "--json", default=None, help="also write raw results to this path"
    )
    parser.add_argument("--headed", action="store_true", help="show the browser window")
    parser.add_argument(
        "--timeout", type=float, default=180.0, help="per step timeout in seconds"
    )
    args = parser.parse_args()

    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print(
            "ERROR: playwright is required. Install with:\n"
            "    pip install playwright\n"
            "(the system Chrome is used, so no browser download is needed)",
            file=sys.stderr,
        )
        return 2

    server = None
    base_url = args.base_url
    if args.start_server or not base_url:
        port = find_free_port()
        base_url = "http://127.0.0.1:%d" % port
        server = start_server(port)

    base_url = base_url.rstrip("/")

    try:
        if not wait_for_server(base_url):
            print("ERROR: dashboard not reachable at %s" % base_url, file=sys.stderr)
            return 2

        tabs = parse_tabs(args.tabs)
        results = []

        with sync_playwright() as playwright:
            try:
                browser = playwright.chromium.launch(
                    channel="chrome", headless=not args.headed
                )
            except Exception:
                browser = playwright.chromium.launch(headless=not args.headed)

            try:
                for _ in range(args.repeat):
                    context = browser.new_context(
                        viewport={"width": 1500, "height": 950},
                        extra_http_headers={"Cache-Control": "no-cache"},
                    )
                    page = context.new_page()
                    results.append(run_once(page, base_url, tabs, args.timeout))
                    context.close()
            finally:
                browser.close()

        print_report(base_url, results)

        if args.json:
            with open(args.json, "w") as json_file:
                json.dump({"base_url": base_url, "runs": results}, json_file, indent=2)
            print("\nraw results written to %s" % args.json)

        loaded = all(
            result["page_load"].get("first_data_seconds") is not None
            for result in results
        )
        return 0 if loaded else 1

    finally:
        if server is not None:
            server.terminate()
            try:
                server.wait(timeout=10)
            except Exception:
                server.kill()


if __name__ == "__main__":
    sys.exit(main())
