"""
BFI IMAX scraper.

Website: https://whatson.bfi.org.uk/imax/Online/
Platform: Tessitura (Online/default.asp), fronted by Cloudflare bot protection.

How it works:
- The venue landing page is itself the full performance listing for BFI IMAX.
  Every performance is embedded in window.articleContext.searchResults, a
  row/column structure keyed by articleContext.searchNames.
- Cloudflare 403s plain HTTP clients, so we drive real Chrome via Playwright
  and wait out the "Just a moment..." interstitial.
- Shared BFI URLs carry an sToken session token that expires. We never reuse
  one; hitting the site root issues a fresh session.
- page_size=200 usually returns everything in one load. Some pages ignore the
  override, so we fall back to walking pages rather than truncating.

Only bookable performances are emitted, matching the other scrapers in this
repo (which likewise skip anything not on sale). BFI IMAX runs long sold-out
blocks - notably The Odyssey in IMAX 70mm - so an empty result here is a
normal state, not a failure. Use watch_bfi_imax.py to track a specific film's
sold-out performances over time.
"""

import html
import re
from datetime import datetime, timedelta
from typing import Optional

from playwright.async_api import async_playwright

from .base import BaseScraper, Screening, Film, Cinema, to_london, now_london


BFI_IMAX = Cinema(
    id="bfi-imax",
    name="BFI IMAX",
    address="1 Charlie Chaplin Walk",
    postcode="SE1 8XR",
    website="https://whatson.bfi.org.uk/imax/Online/",
    chain="BFI",
    lat=51.5110,
    lon=-0.1136,
)

USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
)

# Tessitura status codes, per the site's TabularSearchResultsWidget.js
NOT_YET_ON_SALE = {"C", "C*"}   # sales_status: on sale at a later date
NOT_BOOKABLE = {"S", "U"}       # availability_status: sold out / unavailable

# Fields we pull out of the searchResults row arrays
WANTED_FIELDS = (
    "id", "description", "short_description", "start_date", "sales_status",
    "availability_status", "availability_num", "keywords", "additional_info",
    "venue_short_description", "min_price", "max_price", "data13", "data15",
)


async def launch_browser(playwright):
    """
    Launch a browser, preferring real Chrome.

    Cloudflare treats bundled Chromium more suspiciously than real Chrome, so
    we try the installed Chrome first and fall back to Playwright's Chromium
    (which is what CI runners have by default).
    """
    try:
        return await playwright.chromium.launch(headless=True, channel="chrome")
    except Exception:
        return await playwright.chromium.launch(headless=True)


def is_buyable(row: dict) -> bool:
    """Mirror the site's renderBuyLink logic: would a Buy button be shown?"""
    if row.get("sales_status") in NOT_YET_ON_SALE:
        return False
    return row.get("availability_status") not in NOT_BOOKABLE


class BFIImaxScraper(BaseScraper):
    """Scraper for BFI IMAX using its Tessitura box office pages."""

    BASE_URL = "https://whatson.bfi.org.uk/imax/Online/default.asp"

    def __init__(self):
        super().__init__(BFI_IMAX)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def scrape(self, days_ahead: int = 14) -> list[Screening]:
        """Scrape bookable screenings from BFI IMAX."""
        rows = await self._fetch_rows()

        now = now_london()
        cutoff = now + timedelta(days=days_ahead)

        screenings = []
        sold_out = 0

        for row in rows:
            start_time = self._parse_start(row.get("start_date", ""))
            if start_time is None:
                continue
            if start_time < now or start_time > cutoff:
                continue

            if not is_buyable(row):
                sold_out += 1
                continue

            screenings.append(
                Screening(
                    cinema_id=self.cinema.id,
                    cinema_name=self.cinema.name,
                    film_title=self._clean_title(
                        row.get("description") or row.get("short_description") or ""
                    ),
                    start_time=start_time,
                    booking_url=self._booking_url(row),
                    format=self._format(row),
                    screen=row.get("venue_short_description") or None,
                    notes=self._notes(row),
                )
            )

        if sold_out:
            print(f"  {sold_out} performance(s) in range are sold out / unavailable")

        return screenings

    async def get_films(self) -> list[Film]:
        """Get list of films currently listed at BFI IMAX."""
        rows = await self._fetch_rows()

        films: dict[str, Film] = {}
        for row in rows:
            title = self._clean_title(
                row.get("description") or row.get("short_description") or ""
            )
            if not title or title in films:
                continue
            cert = (row.get("data15") or "").strip()
            films[title] = Film(
                title=title,
                certificate=cert or None,
            )

        return list(films.values())

    # ------------------------------------------------------------------
    # Fetching
    # ------------------------------------------------------------------

    async def _fetch_rows(self) -> list[dict]:
        """Return every performance row listed for the venue."""
        async with async_playwright() as p:
            browser = await launch_browser(p)
            context = await browser.new_context(user_agent=USER_AGENT, locale="en-GB")
            page = await context.new_page()
            try:
                # Establish a fresh session (and clear Cloudflare) at the root.
                await page.goto(self.BASE_URL, wait_until="domcontentloaded",
                                timeout=60000)
                if not await self._settle(page):
                    raise RuntimeError("Cloudflare challenge did not clear")
                await page.wait_for_timeout(1500)

                rows: list[dict] = []
                seen: set[str] = set()
                page_no, total_pages = 1, 1

                while page_no <= total_pages:
                    url = (
                        f"{self.BASE_URL}"
                        f"?BOset::WScontent::SearchResultsInfo::page_size=200"
                        f"&BOset::WScontent::SearchResultsInfo::current_page={page_no}"
                    )
                    await page.goto(url, wait_until="domcontentloaded", timeout=60000)
                    if not await self._settle(page):
                        raise RuntimeError(
                            f"Cloudflare challenge did not clear on page {page_no}"
                        )
                    await page.wait_for_timeout(2500)

                    ctx = await page.evaluate(
                        "() => window.articleContext "
                        "? JSON.parse(JSON.stringify(window.articleContext)) : null"
                    )
                    if not ctx or not ctx.get("searchNames"):
                        raise RuntimeError("articleContext missing - page layout changed")

                    idx = {n: i for i, n in enumerate(ctx["searchNames"])}
                    for r in ctx.get("searchResults", []):
                        row = {k: r[idx[k]] for k in WANTED_FIELDS if k in idx}
                        rid = row.get("id")
                        if rid in seen:
                            continue
                        seen.add(rid)
                        rows.append(row)

                    try:
                        total_pages = int(ctx.get("pagination", {}).get("total_pages", 1))
                    except (TypeError, ValueError):
                        total_pages = 1
                    if total_pages > 40:  # guard against a runaway loop
                        print(f"  warning: {total_pages} pages reported, capping at 40")
                        total_pages = 40
                    page_no += 1

                return rows
            finally:
                await browser.close()

    @staticmethod
    async def _settle(page, timeout_s: int = 45) -> bool:
        """Wait out the Cloudflare interstitial."""
        for _ in range(timeout_s):
            title = ((await page.title()) or "").lower()
            if "just a moment" not in title and "security verification" not in title:
                return True
            await page.wait_for_timeout(1000)
        return False

    # ------------------------------------------------------------------
    # Parsing helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _parse_start(value: str) -> Optional[datetime]:
        """Parse 'Friday 31 July 2026 19:15' into a London-aware datetime."""
        if not value:
            return None
        cleaned = re.sub(r"^[A-Za-z]+\s+", "", value.strip())  # drop weekday
        for fmt in ("%d %B %Y %H:%M", "%d %b %Y %H:%M"):
            try:
                return to_london(datetime.strptime(cleaned, fmt))
            except ValueError:
                continue
        return None

    @staticmethod
    def _clean_title(title: str) -> str:
        # Titles arrive HTML-escaped, e.g. "The Empire Strikes Back&nbsp;"
        title = html.unescape(title or "").replace("\xa0", " ")
        title = re.sub(r"\s+", " ", title).strip()
        # Strip a trailing format tag, e.g. "The Odyssey (IMAX 70mm)"
        title = re.sub(r"\s*\((?:IMAX[^)]*|\d{2}mm[^)]*)\)\s*$", "", title, flags=re.I)
        return title.strip()

    def _booking_url(self, row: dict) -> str:
        """Link to the film's article page where the Buy button lives."""
        info = row.get("additional_info") or ""
        m = re.search(r"article_id=([0-9A-Fa-f\-]{36})", info)
        if m:
            return (
                f"{self.BASE_URL}?doWork::WScontent::getPage="
                f"&BOparam::WScontent::getPage::article_id={m.group(1)}"
            )
        return self.cinema.website

    @staticmethod
    def _format(row: dict) -> Optional[str]:
        """
        Projection format, e.g. 'IMAX 70mm'.

        data13 holds a clean print format when set ('15/70 IMAX'). keywords is
        a comma-separated tag soup mixing formats with season and audience tags
        ('imax,Puppets on Film,Digital,Families'), so we pick out only the tags
        that actually describe projection.
        """
        clean = html.unescape(row.get("data13") or "").strip()
        if clean:
            return clean

        keywords = html.unescape(row.get("keywords") or "")
        formats = []
        for tag in (t.strip() for t in keywords.split(",")):
            if not tag:
                continue
            if re.search(r"imax|\d{2}mm|laser|3d|digital", tag, flags=re.I):
                # Skip content tags that merely mention IMAX, e.g. "IMAX doc"
                if re.search(r"\bdocs?\b", tag, flags=re.I):
                    continue
                if tag not in formats:
                    formats.append(tag)
        return ", ".join(formats) if formats else None

    @staticmethod
    def _notes(row: dict) -> Optional[str]:
        parts = []
        cert = (row.get("data15") or "").strip()
        if cert:
            parts.append(cert)
        avail = row.get("availability_status")
        if avail == "L":
            parts.append("Limited availability")
        return "; ".join(parts) if parts else None


async def main():
    """Test the BFI IMAX scraper."""
    print("=" * 60)
    print("BFI IMAX SCRAPER TEST")
    print("=" * 60)

    scraper = BFIImaxScraper()

    rows = await scraper._fetch_rows()
    print(f"\nTotal performances listed: {len(rows)}")
    bookable = [r for r in rows if is_buyable(r)]
    print(f"Bookable right now: {len(bookable)}")

    films = await scraper.get_films()
    print(f"\nFilms listed ({len(films)}):")
    for f in films:
        cert = f" [{f.certificate}]" if f.certificate else ""
        print(f"  {f.title}{cert}")

    screenings = await scraper.scrape(days_ahead=60)
    print(f"\nBookable screenings in next 60 days: {len(screenings)}")
    for s in sorted(screenings, key=lambda x: x.start_time)[:20]:
        print(f"  {s.start_time.strftime('%a %d %b %H:%M')} - {s.film_title} "
              f"({s.format or '-'})")


if __name__ == '__main__':
    import asyncio
    asyncio.run(main())
