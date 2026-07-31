#!/usr/bin/env python3
"""
BFI IMAX ticket watcher.

Polls a single BFI IMAX article page (Tessitura box office) and reports which
performances are actually buyable. Designed to be run once or twice a day.

Why it works this way:
  - The site sits behind Cloudflare bot protection, so plain httpx/curl gets a
    403 challenge page. We drive real Chrome via Playwright and wait out the
    interstitial.
  - Session tokens (sToken) in shared URLs expire. We never reuse one - we hit
    the site root to establish a fresh session, then load the article by its
    stable article_id.
  - The page embeds every performance in window.articleContext.searchResults,
    a row/column structure keyed by articleContext.searchNames. Setting
    page_size=200 returns all performances in a single load instead of paging
    through 26 pages of 5.

The "is it buyable" rule is copied from the site's own renderer
(Common/Widgets/TabularSearchResultsWidget.js -> renderBuyLink): a Buy button
is shown when sales_status is not 'C'/'C*' (not yet on sale) AND
availability_status is neither 'S' (sold out) nor 'U' (unavailable). We do not
key off availability_num, which can be non-zero or negative on a sold-out show.

Usage:
    python watch_bfi_imax.py                  # check, diff against last run
    python watch_bfi_imax.py --all            # also print every performance
    python watch_bfi_imax.py --no-state       # don't read/write state file
"""

import argparse
import asyncio
import json
import sys
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from playwright.async_api import async_playwright

BASE_URL = "https://whatson.bfi.org.uk/imax/Online/default.asp"
LONDON = ZoneInfo("Europe/London")

USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
)

# Films to watch: label -> article_id (stable; the sToken in a shared URL is not)
WATCHLIST = {
    "The Odyssey": "A0A2A7B6-689F-40DA-A1E4-22F7A5B3E99A",
}

STATE_PATH = Path(__file__).parent / "data" / "bfi_imax_watch_state.json"

# Tessitura status codes, per TabularSearchResultsWidget.js
AVAIL_STATUS = {
    "E": "excellent", "G": "good", "L": "limited",
    "U": "unavailable", "S": "sold out",
}
# sales_status values that mean "on sale at a later date", not bookable now
NOT_YET_ON_SALE = {"C", "C*"}
# availability_status values that mean no Buy button is rendered
NOT_BOOKABLE = {"S", "U"}


def is_buyable(row: dict) -> bool:
    """Mirror the site's renderBuyLink logic: would a Buy button be shown?"""
    if row.get("sales_status") in NOT_YET_ON_SALE:
        return False
    return row.get("availability_status") not in NOT_BOOKABLE


async def _settle_cloudflare(page, timeout_s: int = 45) -> bool:
    """Wait out the Cloudflare 'Just a moment...' interstitial."""
    for _ in range(timeout_s):
        title = (await page.title()) or ""
        low = title.lower()
        if "just a moment" not in low and "security verification" not in low:
            return True
        await page.wait_for_timeout(1000)
    return False


async def fetch_performances(article_id: str, headless: bool = True) -> list[dict]:
    """Return every performance for an article as a list of dicts."""
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=headless, channel="chrome")
        context = await browser.new_context(user_agent=USER_AGENT, locale="en-GB")
        page = await context.new_page()
        try:
            # 1. Establish a fresh session at the site root.
            await page.goto(BASE_URL, wait_until="domcontentloaded", timeout=60000)
            if not await _settle_cloudflare(page):
                raise RuntimeError("Cloudflare challenge did not clear on site root")
            await page.wait_for_timeout(1500)

            # 2. Load the article. page_size=200 usually returns every
            #    performance in one hit, but some articles ignore the override,
            #    so we fall back to walking the pages rather than truncating.
            def article_url(page_no: int) -> str:
                return (
                    f"{BASE_URL}?doWork::WScontent::getPage="
                    f"&BOparam::WScontent::getPage::article_id={article_id}"
                    f"&BOset::WScontent::SearchResultsInfo::page_size=200"
                    f"&BOset::WScontent::SearchResultsInfo::current_page={page_no}"
                )

            wanted = (
                "id", "description", "start_date", "sales_status",
                "availability_status", "availability_num", "min_price",
                "max_price", "venue_short_description", "keywords",
            )

            rows: list[dict] = []
            seen_ids: set[str] = set()
            page_no, total_pages = 1, 1

            while page_no <= total_pages:
                await page.goto(article_url(page_no), wait_until="domcontentloaded",
                                timeout=60000)
                if not await _settle_cloudflare(page):
                    raise RuntimeError(
                        f"Cloudflare challenge did not clear on article page {page_no}"
                    )
                await page.wait_for_timeout(3000)

                ctx = await page.evaluate(
                    "() => window.articleContext "
                    "? JSON.parse(JSON.stringify(window.articleContext)) : null"
                )
                if not ctx or not ctx.get("searchNames"):
                    raise RuntimeError(
                        "articleContext missing - page layout changed "
                        "or article_id is wrong"
                    )

                idx = {n: i for i, n in enumerate(ctx["searchNames"])}
                for r in ctx.get("searchResults", []):
                    row = {k: r[idx[k]] for k in wanted if k in idx}
                    if row.get("id") in seen_ids:
                        continue
                    seen_ids.add(row.get("id"))
                    row["buyable"] = is_buyable(row)
                    rows.append(row)

                try:
                    total_pages = int(ctx.get("pagination", {}).get("total_pages", 1))
                except (TypeError, ValueError):
                    total_pages = 1
                if total_pages > 40:  # sanity guard against a runaway loop
                    print(f"  warning: {total_pages} pages reported, capping at 40",
                          file=sys.stderr)
                    total_pages = 40
                page_no += 1

            return rows
        finally:
            await browser.close()


def load_state() -> dict:
    if STATE_PATH.exists():
        try:
            return json.loads(STATE_PATH.read_text())
        except json.JSONDecodeError:
            return {}
    return {}


def save_state(state: dict) -> None:
    STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    STATE_PATH.write_text(json.dumps(state, indent=1))


def describe(row: dict) -> str:
    avail = AVAIL_STATUS.get(
        row.get("availability_status"), row.get("availability_status")
    )
    return (
        f"{row.get('start_date','?')}  "
        f"[sales={row.get('sales_status')} / {avail} / "
        f"n={row.get('availability_num')}]"
        f"  {row.get('min_price','')}-{row.get('max_price','')}"
    )


async def run(show_all: bool, use_state: bool) -> int:
    now = datetime.now(LONDON)
    state = load_state() if use_state else {}
    new_state = {}
    alerts = []

    print(f"BFI IMAX watcher - {now:%Y-%m-%d %H:%M %Z}\n")

    for label, article_id in WATCHLIST.items():
        print(f"== {label} ==")
        try:
            rows = await fetch_performances(article_id)
        except Exception as exc:
            print(f"  ERROR: {exc}\n", file=sys.stderr)
            # Keep the previous state so a transient failure doesn't fake a diff.
            new_state[label] = state.get(label, {})
            continue

        buyable = [r for r in rows if r["buyable"]]
        prev = state.get(label, {})
        prev_ids = set(prev.get("buyable_ids", []))
        prev_all_ids = set(prev.get("all_ids", []))

        print(f"  {len(rows)} performances, {len(buyable)} on sale")

        if buyable:
            fresh = [r for r in buyable if r["id"] not in prev_ids]
            print("  ON SALE:")
            for r in buyable:
                mark = "NEW " if r["id"] not in prev_ids else "    "
                print(f"    {mark}{describe(r)}")
            if fresh or not prev:
                alerts.append(
                    f"{label}: {len(buyable)} performance(s) on sale"
                    + (f", {len(fresh)} newly" if fresh and prev else "")
                )
        else:
            print("  Nothing on sale - all sold out.")

        # New performances added to the schedule are worth knowing about too.
        if prev_all_ids:
            added = [r for r in rows if r["id"] not in prev_all_ids]
            if added:
                alerts.append(f"{label}: {len(added)} new performance(s) listed")
                print(f"  {len(added)} newly listed performance(s):")
                for r in added:
                    print(f"      {describe(r)}")

        if show_all:
            print("  All performances:")
            for r in rows:
                print(f"      {describe(r)}")

        new_state[label] = {
            "checked_at": now.isoformat(),
            "total": len(rows),
            "buyable_ids": [r["id"] for r in buyable],
            "all_ids": [r["id"] for r in rows],
        }
        print()

    if use_state:
        save_state(new_state)

    if alerts:
        print("*** ALERT ***")
        for a in alerts:
            print(f"  {a}")
        return 10  # distinct exit code so a wrapper can act on it
    print("No change worth flagging.")
    return 0


def main() -> None:
    ap = argparse.ArgumentParser(description="Watch BFI IMAX for ticket availability")
    ap.add_argument("--all", action="store_true", help="print every performance")
    ap.add_argument("--no-state", action="store_true", help="don't read/write state file")
    args = ap.parse_args()
    sys.exit(asyncio.run(run(show_all=args.all, use_state=not args.no_state)))


if __name__ == "__main__":
    main()
