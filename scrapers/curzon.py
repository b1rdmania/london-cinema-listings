"""
Curzon Cinema scraper.

Website: https://www.curzon.com
Platform: Vista Web Client (vwc.curzon.com)

API endpoints (require JWT auth):
  - /ocapi/v1/sites - list of venues
  - /ocapi/v1/films - film catalog
  - /ocapi/v1/showtimes/by-business-date/{date}?siteIds={siteId} - showtimes by date
  - /ocapi/v1/film-screening-dates?siteIds={siteId} - available dates

Authentication: Bearer JWT obtained from browser session.
"""

import asyncio
import httpx
from datetime import datetime, timedelta
from typing import Optional
from playwright.async_api import async_playwright

from .base import BaseScraper, Screening, Film, Cinema, to_london, now_london


# Curzon Hoxton venue info
CURZON_HOXTON = Cinema(
    id="curzon-hoxton",
    name="Curzon Hoxton",
    address="58-60 Hoxton Square",
    postcode="N1 6PB",
    website="https://www.curzon.com/venues/hoxton/",
    chain="Curzon",
    lat=51.5285,
    lon=-0.0815
)

# Vista site IDs for Curzon venues
CURZON_SITE_IDS = {
    "hoxton": "HOX1",
    "soho": "SOH1",
    "mayfair": "MAY1",
    "victoria": "VIC1",
    "bloomsbury": "BLO1",
    "aldgate": "ALD1",
    "kingston": "KIN1",
    "wimbledon": "WIM1",
    "oxford": "OXF1",
    "sheffield": "SHE1",
    "colchester": "COL1",
    "canterbury": "CNT1",
}


class CurzonScraper(BaseScraper):
    """Scraper for Curzon Cinemas using Vista Web Client API."""

    BASE_URL = "https://www.curzon.com"
    API_BASE = "https://vwc.curzon.com/WSVistaWebClient/ocapi/v1"

    def __init__(self, venue: str = "hoxton"):
        """
        Initialize the Curzon scraper.

        Args:
            venue: Venue slug (hoxton, soho, mayfair, etc.)
        """
        self.venue = venue
        self.site_id = CURZON_SITE_IDS.get(venue, "HOX1")

        # Set cinema based on venue
        if venue == "hoxton":
            cinema = CURZON_HOXTON
        else:
            # Create generic cinema for other venues
            cinema = Cinema(
                id=f"curzon-{venue}",
                name=f"Curzon {venue.title()}",
                address="",
                postcode="",
                website=f"https://www.curzon.com/venues/{venue}/",
                chain="Curzon"
            )

        super().__init__(cinema)
        self.auth_token: Optional[str] = None
        self.films_cache: dict = {}

    async def scrape(self, days_ahead: int = 14) -> list[Screening]:
        """Scrape all screenings from Curzon."""
        screenings = []

        # Get auth token via Playwright
        await self._get_auth_token()

        if not self.auth_token:
            print("Warning: Could not obtain auth token")
            return screenings

        async with httpx.AsyncClient(
            headers=self._get_headers(),
            follow_redirects=True,
            timeout=30.0
        ) as client:
            # Get film catalog first
            await self._fetch_films(client)

            # Get screening dates
            dates = await self._get_screening_dates(client)
            if not dates:
                # Fall back to next N days
                dates = [
                    (now_london() + timedelta(days=i)).strftime('%Y-%m-%d')
                    for i in range(days_ahead)
                ]

            print(f"Fetching showtimes for {len(dates)} dates")

            # Fetch showtimes for each date
            for date in dates:
                try:
                    date_screenings = await self._fetch_showtimes(client, date)
                    screenings.extend(date_screenings)
                    if date_screenings:
                        print(f"  {date}: {len(date_screenings)} screenings")
                except Exception as e:
                    print(f"  Error fetching {date}: {e}")

                await asyncio.sleep(0.2)

        return screenings

    async def get_films(self) -> list[Film]:
        """Get list of films currently showing at this Curzon venue."""
        await self._get_auth_token()

        if not self.auth_token:
            return []

        async with httpx.AsyncClient(
            headers=self._get_headers(),
            follow_redirects=True,
            timeout=30.0
        ) as client:
            await self._fetch_films(client)

        return [
            Film(
                title=f.get('title', ''),
                runtime_mins=f.get('runtime'),
                synopsis=f.get('synopsis')
            )
            for f in self.films_cache.values()
        ]

    async def _get_auth_token(self):
        """Get JWT auth token and films data by loading the venue page in a browser."""
        if self.auth_token:
            return

        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            context = await browser.new_context(
                user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)"
            )
            page = await context.new_page()

            async def capture_response(response):
                url = response.url
                if 'vwc.curzon.com' in url and response.status == 200:
                    # Capture auth token
                    request = response.request
                    auth = request.headers.get('authorization', '')
                    if auth.startswith('Bearer '):
                        self.auth_token = auth

                    # Capture films data
                    if '/films' in url and 'availability' not in url:
                        try:
                            data = await response.json()
                            for film in data.get('films', []):
                                film_id = film.get('id')
                                title_data = film.get('title', {})
                                self.films_cache[film_id] = {
                                    'title': title_data.get('text', ''),
                                    'runtime': film.get('runtimeInMinutes'),
                                    'synopsis': film.get('synopsis', {}).get('text', ''),
                                    'release_date': film.get('releaseDate'),
                                    'certificate': film.get('censorRatingId')
                                }
                        except:
                            pass

            page.on('response', capture_response)

            # Load venue page to trigger API calls
            url = f"{self.BASE_URL}/venues/{self.venue}/"
            await page.goto(url, wait_until='networkidle', timeout=60000)
            await page.wait_for_timeout(3000)

            await browser.close()

            if self.films_cache:
                print(f"Cached {len(self.films_cache)} films from browser session")

    def _get_headers(self) -> dict:
        """Get headers for API requests."""
        return {
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)',
            'Accept': 'application/json',
            'Authorization': self.auth_token or '',
            'Origin': 'https://www.curzon.com',
            'Referer': f'https://www.curzon.com/venues/{self.venue}/'
        }

    async def _fetch_films(self, client: httpx.AsyncClient):
        """Fetch and cache film catalog."""
        if self.films_cache:
            return

        try:
            url = f"{self.API_BASE}/films"
            resp = await client.get(url)

            if resp.status_code == 200:
                data = resp.json()
                for film in data.get('films', []):
                    film_id = film.get('id')
                    title_data = film.get('title', {})
                    self.films_cache[film_id] = {
                        'title': title_data.get('text', ''),
                        'runtime': film.get('runtimeInMinutes'),
                        'synopsis': film.get('synopsis', {}).get('text', ''),
                        'release_date': film.get('releaseDate'),
                        'certificate': film.get('censorRatingId')
                    }
        except Exception as e:
            print(f"Error fetching films: {e}")

    async def _get_screening_dates(self, client: httpx.AsyncClient) -> list[str]:
        """Get available screening dates for the venue."""
        try:
            url = f"{self.API_BASE}/film-screening-dates?siteIds={self.site_id}"
            resp = await client.get(url)

            if resp.status_code == 200:
                data = resp.json()
                return data.get('businessDates', [])
        except Exception:
            pass
        return []

    async def _fetch_showtimes(
        self,
        client: httpx.AsyncClient,
        date: str
    ) -> list[Screening]:
        """Fetch showtimes for a specific date."""
        screenings = []

        url = f"{self.API_BASE}/showtimes/by-business-date/{date}?siteIds={self.site_id}"
        resp = await client.get(url)

        if resp.status_code != 200:
            return screenings

        data = resp.json()

        for showtime in data.get('showtimes', []):
            try:
                # Get film info
                film_id = showtime.get('filmId')
                film_info = self.films_cache.get(film_id, {})
                film_title = film_info.get('title', f'Unknown ({film_id})')

                # Parse schedule
                schedule = showtime.get('schedule', {})
                starts_at = schedule.get('startsAt')
                ends_at = schedule.get('endsAt')
                film_starts_at = schedule.get('filmStartsAt')

                if not starts_at:
                    continue

                # Use film start time if available
                start_time_str = film_starts_at or starts_at
                start_time = datetime.fromisoformat(start_time_str.replace('Z', '+00:00'))
                start_time = to_london(start_time)

                end_time = None
                if ends_at:
                    end_time = datetime.fromisoformat(ends_at.replace('Z', '+00:00'))
                    end_time = to_london(end_time)

                # Get screen
                screen_id = showtime.get('screenId', '')
                screen = screen_id.replace(f'{self.site_id}-', 'Screen ') if screen_id else None

                # Build booking URL
                showtime_id = showtime.get('id', '')
                booking_url = f"{self.BASE_URL}/booking/{showtime_id}" if showtime_id else self.cinema.website

                # Check for special attributes
                notes = None
                if showtime.get('requires3dGlasses'):
                    notes = '3D'
                if showtime.get('isSoldOut'):
                    notes = (notes + '; ' if notes else '') + 'Sold Out'

                screening = Screening(
                    cinema_id=self.cinema.id,
                    cinema_name=self.cinema.name,
                    film_title=film_title,
                    start_time=start_time,
                    end_time=end_time,
                    booking_url=booking_url,
                    screen=screen,
                    notes=notes
                )

                screenings.append(screening)

            except Exception as e:
                continue

        return screenings


async def main():
    """Test the Curzon scraper."""
    import json
    from dataclasses import asdict

    print("=" * 60)
    print("CURZON HOXTON SCRAPER TEST")
    print("=" * 60)

    scraper = CurzonScraper(venue="hoxton")
    screenings = await scraper.scrape(days_ahead=7)

    # Sort by datetime
    screenings.sort(key=lambda s: s.start_time)

    print(f"\nTotal screenings found: {len(screenings)}")

    print("\nUpcoming screenings:")
    for s in screenings[:20]:
        screen_info = f" [{s.screen}]" if s.screen else ""
        end_info = f" -> {s.end_time.strftime('%H:%M')}" if s.end_time else ""
        print(f"  {s.start_time.strftime('%a %d %b %H:%M')}{end_info}{screen_info} - {s.film_title}")

    # Group by film
    films = {}
    for s in screenings:
        if s.film_title not in films:
            films[s.film_title] = []
        films[s.film_title].append(s)

    print(f"\n{len(films)} unique films with screenings:")
    for title, shows in sorted(films.items()):
        print(f"  {title}: {len(shows)} screenings")

    # Export to JSON
    output = []
    for s in screenings:
        d = asdict(s)
        d['start_time'] = s.start_time.isoformat()
        d['scraped_at'] = s.scraped_at.isoformat()
        if s.end_time:
            d['end_time'] = s.end_time.isoformat()
        output.append(d)

    with open('data/curzon_screenings.json', 'w') as f:
        json.dump(output, f, indent=2)

    print(f"\nExported {len(output)} screenings to data/curzon_screenings.json")


if __name__ == '__main__':
    asyncio.run(main())
