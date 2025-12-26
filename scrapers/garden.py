"""
Garden Cinema scraper.

Website: https://thegardencinema.co.uk
Platform: Savoy Systems ticketing (TheGardenCinema.dll routes)

Data source: HTML parsing of the homepage which shows all current screenings
grouped by date.

Structure:
- date-block: contains date header + film blocks
  - h2.films-list__by-date__date__title: "Friday 26 December"
  - div.films-list__by-date__film: individual film
    - h1.films-list__by-date__film__title: "The Shining15" (title + cert)
    - div.films-list__by-date__film__stats: "Stanley Kubrick, USA, UK, 1980, 142m."
    - div.films-list__by-date__film__screeningtimes: screening times
      - span.screening-time > a: booking link with time
"""

import asyncio
import re
from datetime import datetime, timedelta
from typing import Optional
from bs4 import BeautifulSoup
import httpx

from .base import BaseScraper, Screening, Film, Cinema, to_london, now_london


# Garden Cinema venue info
GARDEN_CINEMA = Cinema(
    id="garden-cinema",
    name="The Garden Cinema",
    address="39-41 Parker Street",
    postcode="WC2B 5PQ",
    website="https://thegardencinema.co.uk",
    chain="Independent",
    lat=51.5160,
    lon=-0.1224
)


class GardenScraper(BaseScraper):
    """Scraper for The Garden Cinema using HTML parsing."""

    BASE_URL = "https://www.thegardencinema.co.uk"

    def __init__(self):
        super().__init__(GARDEN_CINEMA)

    async def scrape(self, days_ahead: int = 14) -> list[Screening]:
        """Scrape all screenings from The Garden Cinema."""
        screenings = []

        async with httpx.AsyncClient(
            headers={
                "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
                "Accept": "text/html,application/xhtml+xml",
            },
            follow_redirects=True,
            timeout=30.0
        ) as client:
            response = await client.get(self.BASE_URL)
            soup = BeautifulSoup(response.text, 'lxml')

            cutoff_date = now_london() + timedelta(days=days_ahead)
            current_year = now_london().year

            # Find all date blocks
            date_blocks = soup.find_all('div', class_='date-block')

            for date_block in date_blocks:
                # Get the date for this block
                date_header = date_block.find('h2', class_='films-list__by-date__date__title')
                if not date_header:
                    continue

                date_str = date_header.get_text(strip=True)
                screening_date = self._parse_date(date_str, current_year)

                if screening_date > cutoff_date.date():
                    continue

                # Find all films in this date block
                film_blocks = date_block.find_all('div', class_='films-list__by-date__film')

                for film_block in film_blocks:
                    try:
                        film_screenings = self._parse_film_block(film_block, screening_date)
                        screenings.extend(film_screenings)
                    except Exception as e:
                        continue

        # Deduplicate by booking URL
        seen = set()
        unique = []
        for s in screenings:
            if s.booking_url not in seen:
                seen.add(s.booking_url)
                unique.append(s)

        print(f"Found {len(unique)} screenings at Garden Cinema")
        return unique

    def _parse_film_block(self, film_block, screening_date) -> list[Screening]:
        """Parse a film block to extract all screenings."""
        screenings = []

        # Get film title
        title_el = film_block.find('h1', class_='films-list__by-date__film__title')
        if not title_el:
            return screenings

        raw_title = title_el.get_text(strip=True)

        # Clean title - remove certificate rating at the end (e.g., "The Shining15" -> "The Shining")
        # Certificates: U, PG, 12, 12A, 15, 18, TBC
        film_title = re.sub(r'(U|PG|12A?|15|18|TBC)$', '', raw_title).strip()

        # Also handle cases like "Film Title- Family ScreeningU"
        film_title = re.sub(r'-\s*(Family Screening|Members Only|Q&A).*$', '', film_title, flags=re.I).strip()

        if not film_title:
            return screenings

        # Get film stats for additional info
        notes = None
        stats_el = film_block.find('div', class_='films-list__by-date__film__stats')
        if stats_el:
            stats_text = stats_el.get_text(strip=True)
            # Extract format info like "35mm" or "16mm"
            format_match = re.search(r'(\d+mm)', stats_text, re.I)
            if format_match:
                notes = format_match.group(1)

        # Check if it's a special screening
        season_link = film_block.find('span', class_='films-list__by-date__film__season__link')
        if season_link:
            season_text = season_link.get_text(strip=True)
            if 'Family' in season_text:
                notes = 'Family Screening' if not notes else f"{notes}; Family Screening"

        # Find all screening times
        screeningtimes = film_block.find('div', class_='films-list__by-date__film__screeningtimes')
        if not screeningtimes:
            return screenings

        time_links = screeningtimes.find_all('a', href=re.compile(r'TcsPerformance'))

        for link in time_links:
            time_text = link.get_text(strip=True)

            # Skip sold out screenings
            if 'sold out' in time_text.lower():
                continue

            # Parse time (e.g., "17:00" or "17.00")
            time_match = re.search(r'(\d{1,2})[:\.](\d{2})', time_text)
            if not time_match:
                continue

            hour = int(time_match.group(1))
            minute = int(time_match.group(2))

            try:
                start_time = datetime.combine(
                    screening_date,
                    datetime.min.time().replace(hour=hour, minute=minute)
                )
                start_time = to_london(start_time)
            except:
                continue

            booking_url = link.get('href', '')

            # Check for audio description or other accessibility notes
            screening_notes = notes
            parent_panel = link.find_parent('div', class_='screening-panel')
            if parent_panel and 'audio_description' in parent_panel.get('class', []):
                screening_notes = 'Audio Description' if not screening_notes else f"{screening_notes}; Audio Description"

            screenings.append(Screening(
                cinema_id=self.cinema.id,
                cinema_name=self.cinema.name,
                film_title=film_title,
                start_time=start_time,
                booking_url=booking_url,
                notes=screening_notes,
            ))

        return screenings

    def _parse_date(self, date_str: str, current_year: int) -> datetime.date:
        """Parse a date string like 'Friday 26 December'."""
        if not date_str:
            return now_london().date()

        # Remove day name
        date_str = re.sub(r'^(Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday)\s*', '', date_str, flags=re.I)
        date_str = date_str.strip()

        # Try to parse "26 December"
        try:
            parsed = datetime.strptime(date_str, "%d %B")
            result = parsed.replace(year=current_year)
            # If date is in the past (more than a day ago), assume next year
            if result.date() < now_london().date() - timedelta(days=1):
                result = result.replace(year=current_year + 1)
            return result.date()
        except ValueError:
            pass

        return now_london().date()

    async def get_films(self) -> list[Film]:
        """Get list of films currently showing."""
        screenings = await self.scrape(days_ahead=14)

        films_dict = {}
        for s in screenings:
            if s.film_title not in films_dict:
                films_dict[s.film_title] = Film(title=s.film_title)

        return list(films_dict.values())


async def main():
    """Test the Garden Cinema scraper."""
    print("=" * 60)
    print("GARDEN CINEMA SCRAPER TEST")
    print("=" * 60)

    scraper = GardenScraper()
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
