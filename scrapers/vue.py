"""
Vue Cinema scraper (Islington).

Website: https://www.myvue.com
Platform: Sitecore CMS with microservices API

API endpoints:
- /api/microservice/showings/cinemas/{id}/films - showtimes by cinema
- /api/microservice/showings/showingDates - available dates

Cinema ID for Vue Islington: 10032
"""

import asyncio
import re
from datetime import datetime, timedelta
from typing import Optional
from playwright.async_api import async_playwright

from .base import BaseScraper, Screening, Film, Cinema, to_london


# Vue Islington venue info
VUE_ISLINGTON = Cinema(
    id="vue-islington",
    name="Vue Islington",
    address="36 Parkfield Street, Islington",
    postcode="N1 0PS",
    website="https://www.myvue.com/cinema/islington",
    chain="Vue",
    lat=51.5344,
    lon=-0.1057
)


class VueScraper(BaseScraper):
    """Scraper for Vue Islington using their microservices API."""

    BASE_URL = "https://www.myvue.com"
    CINEMA_ID = "10032"

    def __init__(self):
        super().__init__(VUE_ISLINGTON)
        self.showings_data = None
        self.showing_dates = []

    async def scrape(self, days_ahead: int = 14) -> list[Screening]:
        """Scrape all screenings from Vue Islington."""
        all_screenings = []

        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            context = await browser.new_context(
                user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"
            )
            page = await context.new_page()

            # Capture API responses
            async def handle_response(response):
                url = response.url
                if response.status == 200:
                    try:
                        if f'/cinemas/{self.CINEMA_ID}/films' in url:
                            self.showings_data = await response.json()
                        elif '/showingDates' in url and self.CINEMA_ID in url:
                            data = await response.json()
                            self.showing_dates = data.get('result', [])
                    except:
                        pass

            page.on('response', handle_response)

            # Load venue page to trigger API calls
            print(f"Loading Vue Islington page...")
            await page.goto(
                f"{self.BASE_URL}/cinema/islington/whats-on",
                wait_until='networkidle',
                timeout=60000
            )
            await page.wait_for_timeout(3000)

            # Parse today's showings
            if self.showings_data and self.showings_data.get('result'):
                screenings = self._parse_showings(self.showings_data['result'])
                all_screenings.extend(screenings)
                print(f"  Today: {len(screenings)} screenings")

            # Try to get more dates
            if self.showing_dates and len(self.showing_dates) > 1:
                for date_info in self.showing_dates[1:min(days_ahead, len(self.showing_dates))]:
                    date_str = date_info.get('date', '')
                    if not date_str:
                        continue

                    try:
                        # Click on date or navigate to date-specific URL
                        date_url = f"{self.BASE_URL}/cinema/islington/whats-on?date={date_str[:10]}"
                        self.showings_data = None

                        await page.goto(date_url, wait_until='networkidle', timeout=30000)
                        await page.wait_for_timeout(1500)

                        if self.showings_data and self.showings_data.get('result'):
                            screenings = self._parse_showings(self.showings_data['result'])
                            all_screenings.extend(screenings)
                            print(f"  {date_str[:10]}: {len(screenings)} screenings")
                    except Exception as e:
                        continue

            await browser.close()

        # Deduplicate by session ID
        seen = set()
        unique = []
        for s in all_screenings:
            # Extract session ID from booking URL
            session_id = s.booking_url.split('/')[-1] if s.booking_url else None
            key = session_id or (s.film_title, s.start_time.isoformat())
            if key not in seen:
                seen.add(key)
                unique.append(s)

        print(f"Found {len(unique)} total screenings at Vue Islington")
        return unique

    def _parse_showings(self, films_data: list) -> list[Screening]:
        """Parse showings from Vue API response."""
        screenings = []

        for film in films_data:
            film_title = film.get('filmTitle', '')
            if not film_title:
                continue

            # Get film attributes for notes
            film_attrs = []
            for attr in film.get('filmAttributes', []):
                name = attr.get('shortName') or attr.get('name')
                if name and name not in ['AD', 'Lux']:  # Skip common ones
                    film_attrs.append(name)

            for group in film.get('showingGroups', []):
                for session in group.get('sessions', []):
                    try:
                        start_time_str = session.get('startTime')
                        if not start_time_str:
                            continue

                        start_time = datetime.fromisoformat(start_time_str)
                        start_time = to_london(start_time)

                        end_time = None
                        end_time_str = session.get('endTime')
                        if end_time_str:
                            end_time = datetime.fromisoformat(end_time_str)
                            end_time = to_london(end_time)

                        # Build booking URL
                        booking_path = session.get('bookingUrl', '')
                        booking_url = f"{self.BASE_URL}{booking_path}" if booking_path else self.cinema.website

                        # Build notes from session attributes
                        notes_parts = []
                        for attr in session.get('attributes', []):
                            short_name = attr.get('shortName')
                            if short_name and short_name not in ['AD', 'Lux', 'Strobe FX', 'English']:
                                notes_parts.append(short_name)

                        notes = '; '.join(notes_parts) if notes_parts else None

                        screenings.append(Screening(
                            cinema_id=self.cinema.id,
                            cinema_name=self.cinema.name,
                            film_title=film_title,
                            start_time=start_time,
                            end_time=end_time,
                            booking_url=booking_url,
                            notes=notes,
                        ))
                    except Exception as e:
                        continue

        return screenings

    async def get_films(self) -> list[Film]:
        """Get list of films currently showing."""
        screenings = await self.scrape(days_ahead=7)

        films_dict = {}
        for s in screenings:
            if s.film_title not in films_dict:
                films_dict[s.film_title] = Film(title=s.film_title)

        return list(films_dict.values())


async def main():
    """Test the Vue Islington scraper."""
    print("=" * 60)
    print("VUE ISLINGTON SCRAPER TEST")
    print("=" * 60)

    scraper = VueScraper()
    screenings = await scraper.scrape(days_ahead=7)

    print(f"\nTotal screenings found: {len(screenings)}")

    # Sort by datetime
    screenings.sort(key=lambda s: s.start_time)

    print("\nUpcoming screenings:")
    for s in screenings[:20]:
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
