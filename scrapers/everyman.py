"""
Everyman Cinema scraper (Broadgate).

Website: https://www.everymancinema.com
Platform: Gatsby + GraphQL backend

Data source: DOM parsing of rendered venue showtimes page.
Showtimes are loaded dynamically via JavaScript.

Structure:
- H3 elements contain movie titles with certificates (e.g., "Marty Supreme15")
- Walking up 4 levels from H3 finds container with purchase links
- Purchase links have aria-label with time (e.g., "19:45")
- Date selector buttons: Today, Tomorrow, Next 7 days
"""

import asyncio
import re
from datetime import datetime, timedelta
from typing import Optional
from playwright.async_api import async_playwright

from .base import BaseScraper, Screening, Film, Cinema


# Everyman Broadgate venue info
EVERYMAN_BROADGATE = Cinema(
    id="everyman-broadgate",
    name="Everyman Broadgate",
    address="35 Broadgate Circle",
    postcode="EC2M 2QS",
    website="https://www.everymancinema.com/venues-list/x11nt-everyman-broadgate/",
    chain="Everyman",
    lat=51.5197,
    lon=-0.0841
)


class EverymanScraper(BaseScraper):
    """Scraper for Everyman Broadgate using Playwright DOM parsing."""

    BASE_URL = "https://www.everymancinema.com"
    VENUE_URL = "https://www.everymancinema.com/venues-list/x11nt-everyman-broadgate/"
    THEATER_CODE = "X11NT"

    def __init__(self):
        super().__init__(EVERYMAN_BROADGATE)

    async def scrape(self, days_ahead: int = 14) -> list[Screening]:
        """Scrape all screenings from Everyman Broadgate."""
        all_screenings = []

        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            context = await browser.new_context(
                user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"
            )
            page = await context.new_page()

            # Navigate to venue page
            print(f"Loading Everyman Broadgate page...")
            await page.goto(self.VENUE_URL, wait_until='networkidle', timeout=60000)
            await page.wait_for_timeout(2000)

            # Get available date options
            date_buttons = await page.query_selector_all('button')
            date_options = []
            for btn in date_buttons:
                text = await btn.text_content()
                if text and any(x in text.lower() for x in ['today', 'tomorrow', '7 days', 'next']):
                    date_options.append((btn, text.strip()))

            # Scrape "Today" first (default view)
            today = datetime.now().date()
            today_screenings = await self._extract_showtimes(page, today)
            all_screenings.extend(today_screenings)
            print(f"  Today: {len(today_screenings)} screenings")

            # Try to click "Tomorrow" and scrape
            for btn, text in date_options:
                if 'tomorrow' in text.lower():
                    try:
                        await btn.click()
                        await page.wait_for_timeout(1500)
                        tomorrow = today + timedelta(days=1)
                        tomorrow_screenings = await self._extract_showtimes(page, tomorrow)
                        all_screenings.extend(tomorrow_screenings)
                        print(f"  Tomorrow: {len(tomorrow_screenings)} screenings")
                    except:
                        pass
                    break

            # Try "Next 7 days" for more coverage
            for btn, text in date_options:
                if '7 days' in text.lower() or 'next' in text.lower():
                    try:
                        await btn.click()
                        await page.wait_for_timeout(2000)
                        # This view might show multiple days
                        week_screenings = await self._extract_showtimes_with_dates(page)
                        all_screenings.extend(week_screenings)
                        print(f"  Week view: {len(week_screenings)} screenings")
                    except:
                        pass
                    break

            await browser.close()

        # Deduplicate by booking URL
        seen = set()
        unique = []
        for s in all_screenings:
            key = s.booking_url or (s.film_title, s.start_time.isoformat())
            if key not in seen:
                seen.add(key)
                unique.append(s)

        print(f"Found {len(unique)} total screenings at Everyman Broadgate")
        return unique

    async def _extract_showtimes(self, page, date) -> list[Screening]:
        """Extract showtimes for a specific date from the current page view."""
        screenings = []

        # Find H3 movie titles and their showtime containers
        data = await page.evaluate('''() => {
            const results = [];
            const h3s = document.querySelectorAll('h3');

            for (const h3 of h3s) {
                const text = h3.textContent.trim();
                // Movie titles end with certificate ratings
                if (!text.match(/(U|PG|12A?|15|18|TBC)$/)) continue;

                // Walk up to find container with purchase links
                let container = h3.parentElement;
                let times = [];
                let depth = 0;

                while (container && depth < 10 && times.length === 0) {
                    const links = container.querySelectorAll('a[href*="purchase"]');
                    times = [...links].map(a => ({
                        time: a.getAttribute('aria-label') || a.textContent.trim(),
                        url: a.href
                    }));
                    container = container.parentElement;
                    depth++;
                }

                if (times.length > 0) {
                    results.push({
                        title: text,
                        times: times
                    });
                }
            }

            return results;
        }''')

        for item in data:
            film_title = self._clean_title(item.get('title', ''))
            if not film_title:
                continue

            for time_info in item.get('times', []):
                try:
                    time_str = time_info.get('time', '')
                    booking_url = time_info.get('url', '')

                    # Parse time (e.g., "19:45")
                    time_match = re.match(r'(\d{1,2}):(\d{2})', time_str)
                    if not time_match:
                        continue

                    hour = int(time_match.group(1))
                    minute = int(time_match.group(2))
                    start_time = datetime.combine(date, datetime.min.time().replace(hour=hour, minute=minute))

                    screenings.append(Screening(
                        cinema_id=self.cinema.id,
                        cinema_name=self.cinema.name,
                        film_title=film_title,
                        start_time=start_time,
                        booking_url=booking_url or self.VENUE_URL,
                    ))
                except:
                    continue

        return screenings

    async def _extract_showtimes_with_dates(self, page) -> list[Screening]:
        """Extract showtimes from a view that might show multiple dates."""
        screenings = []
        today = datetime.now().date()

        # Similar extraction but try to detect date context
        data = await page.evaluate('''() => {
            const results = [];
            const h3s = document.querySelectorAll('h3');

            for (const h3 of h3s) {
                const text = h3.textContent.trim();
                if (!text.match(/(U|PG|12A?|15|18|TBC)$/)) continue;

                let container = h3.parentElement;
                let times = [];
                let depth = 0;

                while (container && depth < 10 && times.length === 0) {
                    const links = container.querySelectorAll('a[href*="purchase"]');
                    times = [...links].map(a => ({
                        time: a.getAttribute('aria-label') || a.textContent.trim(),
                        url: a.href
                    }));
                    container = container.parentElement;
                    depth++;
                }

                if (times.length > 0) {
                    results.push({
                        title: text,
                        times: times
                    });
                }
            }

            return results;
        }''')

        for item in data:
            film_title = self._clean_title(item.get('title', ''))
            if not film_title:
                continue

            for time_info in item.get('times', []):
                try:
                    time_str = time_info.get('time', '')
                    booking_url = time_info.get('url', '')

                    time_match = re.match(r'(\d{1,2}):(\d{2})', time_str)
                    if not time_match:
                        continue

                    hour = int(time_match.group(1))
                    minute = int(time_match.group(2))

                    # Default to today, adjust if time has passed
                    screening_date = today
                    test_time = datetime.combine(screening_date, datetime.min.time().replace(hour=hour, minute=minute))
                    if test_time < datetime.now():
                        screening_date = today + timedelta(days=1)

                    start_time = datetime.combine(screening_date, datetime.min.time().replace(hour=hour, minute=minute))

                    screenings.append(Screening(
                        cinema_id=self.cinema.id,
                        cinema_name=self.cinema.name,
                        film_title=film_title,
                        start_time=start_time,
                        booking_url=booking_url or self.VENUE_URL,
                    ))
                except:
                    continue

        return screenings

    def _clean_title(self, title: str) -> str:
        """Clean up film title - remove certificate ratings."""
        if not title:
            return ''

        # Remove certificate ratings at the end (U, PG, 12, 12A, 15, 18, TBC)
        title = re.sub(r'(U|PG|12A|12|15|18|TBC)$', '', title).strip()

        return title

    async def get_films(self) -> list[Film]:
        """Get list of films currently showing."""
        screenings = await self.scrape(days_ahead=14)

        films_dict = {}
        for s in screenings:
            if s.film_title not in films_dict:
                films_dict[s.film_title] = Film(title=s.film_title)

        return list(films_dict.values())


async def main():
    """Test the Everyman Broadgate scraper."""
    print("=" * 60)
    print("EVERYMAN BROADGATE SCRAPER TEST")
    print("=" * 60)

    scraper = EverymanScraper()
    screenings = await scraper.scrape(days_ahead=14)

    print(f"\nTotal screenings found: {len(screenings)}")

    # Sort by datetime
    screenings.sort(key=lambda s: s.start_time)

    print("\nUpcoming screenings:")
    for s in screenings[:25]:
        notes = f" [{s.notes}]" if s.notes else ""
        print(f"  {s.start_time.strftime('%a %d %b %H:%M')} - {s.film_title}{notes}")

    # Group by film
    films = {}
    for s in screenings:
        if s.film_title not in films:
            films[s.film_title] = []
        films[s.film_title].append(s)

    print(f"\n{len(films)} unique films:")
    for title, shows in sorted(films.items()):
        print(f"  {title}: {len(shows)} screenings")


if __name__ == '__main__':
    asyncio.run(main())
