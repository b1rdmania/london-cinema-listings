"""
Prince Charles Cinema scraper.

Website: https://princecharlescinema.com
Platform: WordPress with jacro-plugin

Data source: Server-rendered HTML on the What's On page.
No API or JavaScript rendering required - simple httpx + BeautifulSoup.

The cinema is famous for:
- Repertory/classic films
- 35mm and 70mm screenings
- Sing-Along-A shows
- All-night marathons
- £1 member screenings
"""

import asyncio
import re
from datetime import datetime, timedelta
from typing import Optional

import httpx
from bs4 import BeautifulSoup

from .base import BaseScraper, Screening, Film, Cinema, to_london, now_london


# Prince Charles Cinema venue info
PRINCE_CHARLES_CINEMA = Cinema(
    id="prince-charles-cinema",
    name="Prince Charles Cinema",
    address="7 Leicester Place",
    postcode="WC2H 7BY",
    website="https://princecharlescinema.com/",
    chain=None,  # Independent
    lat=51.5112,
    lon=-0.1304
)

# Format tag normalization
FORMAT_TAGS = {
    '4k': '4K',
    '35mm': '35mm',
    '70mm': '70mm',
    'sub': 'Subtitled',
    'dub': 'Dubbed',
    'intro': 'Intro',
    'qa': 'Q&A',
    '£1 mem': '£1 Members',
    'sing': 'Sing-Along',
}


class PrinceCharlesScraper(BaseScraper):
    """Scraper for Prince Charles Cinema using server-rendered HTML."""

    BASE_URL = "https://princecharlescinema.com"
    WHATSON_URL = f"{BASE_URL}/whats-on/"

    def __init__(self):
        """Initialize the Prince Charles scraper."""
        super().__init__(PRINCE_CHARLES_CINEMA)

    async def scrape(self, days_ahead: int = 14) -> list[Screening]:
        """
        Scrape all screenings from Prince Charles Cinema.

        Note: The What's On page shows all upcoming screenings (several months),
        so the days_ahead parameter is only used for filtering results.
        """
        screenings = []

        async with httpx.AsyncClient(
            headers={
                'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)'
            },
            follow_redirects=True,
            timeout=30.0
        ) as client:
            try:
                resp = await client.get(self.WHATSON_URL)
                if resp.status_code != 200:
                    print(f"Error fetching What's On page: {resp.status_code}")
                    return screenings

                html = resp.text
                screenings = self._parse_whatson_page(html)

                # Filter to requested date range if needed
                if days_ahead:
                    cutoff = now_london().replace(hour=0, minute=0, second=0, microsecond=0)
                    cutoff_end = cutoff + timedelta(days=days_ahead)
                    screenings = [
                        s for s in screenings
                        if cutoff <= s.start_time < cutoff_end
                    ]

            except Exception as e:
                print(f"Error scraping Prince Charles: {e}")

        return screenings

    async def get_films(self) -> list[Film]:
        """Get list of films currently showing at Prince Charles Cinema."""
        films = []
        seen_titles = set()

        async with httpx.AsyncClient(
            headers={
                'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)'
            },
            follow_redirects=True,
            timeout=30.0
        ) as client:
            try:
                resp = await client.get(self.WHATSON_URL)
                if resp.status_code != 200:
                    return films

                soup = BeautifulSoup(resp.text, 'lxml')

                for film_div in soup.find_all('div', class_='film_list-outer'):
                    film_data = self._parse_film_data(film_div)
                    if film_data and film_data['title'] not in seen_titles:
                        seen_titles.add(film_data['title'])
                        films.append(Film(
                            title=film_data['title'],
                            runtime_mins=film_data.get('runtime'),
                            year=film_data.get('year'),
                            certificate=film_data.get('certificate'),
                            synopsis=film_data.get('synopsis'),
                            director=film_data.get('director')
                        ))

            except Exception as e:
                print(f"Error fetching films: {e}")

        return films

    def _parse_whatson_page(self, html: str) -> list[Screening]:
        """Parse the What's On HTML page into Screening objects."""
        screenings = []
        soup = BeautifulSoup(html, 'lxml')

        for film_div in soup.find_all('div', class_='film_list-outer'):
            film_data = self._parse_film_data(film_div)
            if not film_data:
                continue

            film_screenings = self._parse_performances(film_div, film_data)
            screenings.extend(film_screenings)

        # Sort by start time
        screenings.sort(key=lambda s: s.start_time)

        return screenings

    def _parse_film_data(self, film_div) -> Optional[dict]:
        """Extract film metadata from a film listing div."""
        # Get film title
        title_el = film_div.find('a', class_='liveeventtitle')
        if not title_el:
            return None

        title = title_el.get_text(strip=True)
        film_url = title_el.get('href', '')

        # Parse metadata from running-time div
        runtime_div = film_div.find('div', class_='running-time')
        year = None
        runtime = None
        certificate = None
        country = None
        genre = None

        if runtime_div:
            spans = runtime_div.find_all('span')
            for span in spans:
                text = span.get_text(strip=True)
                # Year (4 digit number)
                if re.match(r'^\d{4}$', text):
                    year = int(text)
                # Runtime (e.g. "114mins")
                elif 'min' in text.lower():
                    match = re.match(r'(\d+)', text)
                    if match:
                        runtime = int(match.group(1))
                # Certificate (e.g. "(U)", "(12A)", "(PG)")
                elif text.startswith('(') and text.endswith(')'):
                    cert = text[1:-1]
                    if cert in ('U', 'PG', '12', '12A', '15', '18', 'R18', 'TBC'):
                        certificate = cert
                    else:
                        # Could be a country or genre
                        if len(text) <= 5:
                            country = cert
                        else:
                            genre = cert

        # Get director and cast from film-info div
        director = None
        cast = None
        film_info = film_div.find('div', class_='film-info')
        if film_info:
            for span in film_info.find_all('span'):
                text = span.get_text(strip=True)
                if text.startswith('Directed by'):
                    director = text.replace('Directed by', '').strip()
                elif text.startswith('Starring'):
                    cast = text.replace('Starring', '').strip()

        # Get synopsis
        synopsis = None
        synopsis_div = film_div.find('div', class_='jacro-formatted-text')
        if synopsis_div:
            # Get text from all paragraphs
            paragraphs = synopsis_div.find_all('p')
            synopsis_parts = [p.get_text(strip=True) for p in paragraphs if p.get_text(strip=True)]
            synopsis = ' '.join(synopsis_parts)

        return {
            'title': title,
            'film_url': film_url,
            'year': year,
            'runtime': runtime,
            'certificate': certificate,
            'country': country,
            'genre': genre,
            'director': director,
            'cast': cast,
            'synopsis': synopsis
        }

    def _parse_performances(self, film_div, film_data: dict) -> list[Screening]:
        """Extract performance times from a film listing div."""
        screenings = []

        perf_outer = film_div.find('div', class_='performance-list-items-outer')
        if not perf_outer:
            return screenings

        current_date = None
        current_year = now_london().year
        current_month = now_london().month

        for elem in perf_outer.find_all(['div', 'li', 'ul']):
            # Date heading (e.g. "Friday 26th December")
            if 'heading' in elem.get('class', []):
                date_text = elem.get_text(strip=True)
                current_date = self._parse_date_heading(date_text, current_year, current_month)
                continue

            # Booking button within <li>
            if elem.name == 'li':
                book_btn = elem.find('a', class_='film_book_button')
                if not book_btn or not current_date:
                    continue

                # Check for sold out
                is_sold_out = 'soldfilm_book_button' in ' '.join(elem.get('class', []))

                time_span = book_btn.find('span', class_='time')
                if not time_span:
                    continue

                time_text = time_span.get_text(strip=True)
                booking_url = book_btn.get('href', '')

                # Parse time and convert to London timezone
                start_time = self._parse_time(time_text, current_date)
                if not start_time:
                    continue
                start_time = to_london(start_time)

                # Get format tags (4K, 35mm, etc)
                format_tags = self._extract_format_tags(elem)

                # Build notes
                notes_parts = []
                if format_tags:
                    notes_parts.extend(format_tags)
                if is_sold_out:
                    notes_parts.append('Sold Out')

                # Calculate end time if we have runtime
                end_time = None
                if film_data.get('runtime'):
                    end_time = start_time + timedelta(minutes=film_data['runtime'])

                screening = Screening(
                    cinema_id=self.cinema.id,
                    cinema_name=self.cinema.name,
                    film_title=film_data['title'],
                    start_time=start_time,
                    end_time=end_time,
                    booking_url=booking_url or self.cinema.website,
                    notes='; '.join(notes_parts) if notes_parts else None
                )

                screenings.append(screening)

        return screenings

    def _parse_date_heading(self, date_text: str, current_year: int, current_month: int) -> Optional[datetime]:
        """Parse a date heading like 'Friday 26th December'."""
        try:
            # Remove ordinal suffix (1st, 2nd, 3rd, 4th, etc.)
            date_clean = re.sub(r'(\d+)(st|nd|rd|th)', r'\1', date_text)

            # Try to parse with year
            parsed = datetime.strptime(f"{date_clean} {current_year}", "%A %d %B %Y")

            # Handle year boundary (dates in early year when current month is late in year)
            if parsed.month < current_month - 1:
                parsed = parsed.replace(year=current_year + 1)

            return parsed

        except ValueError:
            return None

    def _parse_time(self, time_text: str, date: datetime) -> Optional[datetime]:
        """Parse a time string like '2:30 pm' and combine with date."""
        try:
            # Parse time
            time_obj = datetime.strptime(time_text.strip(), "%I:%M %p")
            return date.replace(
                hour=time_obj.hour,
                minute=time_obj.minute,
                second=0,
                microsecond=0
            )
        except ValueError:
            return None

    def _extract_format_tags(self, li_elem) -> list[str]:
        """Extract format tags from a performance list item."""
        format_tags = []

        # Check movietag div for explicit tags
        movietag = li_elem.find('div', class_='movietag')
        if movietag:
            for tag in movietag.find_all('span', class_='tag'):
                tag_text = tag.get_text(strip=True)
                # Normalize the tag
                normalized = FORMAT_TAGS.get(tag_text.lower(), tag_text)
                if normalized and normalized not in format_tags:
                    format_tags.append(normalized)

        # Also check li element's class for format indicators
        li_classes = li_elem.get('class', [])
        for cls in li_classes:
            cls_lower = cls.lower()
            if cls_lower in FORMAT_TAGS:
                normalized = FORMAT_TAGS[cls_lower]
                if normalized not in format_tags:
                    format_tags.append(normalized)

        return format_tags


async def main():
    """Test the Prince Charles Cinema scraper."""
    import json
    from dataclasses import asdict

    print("=" * 60)
    print("PRINCE CHARLES CINEMA SCRAPER TEST")
    print("=" * 60)

    scraper = PrinceCharlesScraper()
    screenings = await scraper.scrape(days_ahead=14)

    print(f"\nTotal screenings found: {len(screenings)}")

    print("\nUpcoming screenings:")
    for s in screenings[:20]:
        notes_info = f" [{s.notes}]" if s.notes else ""
        end_info = f" -> {s.end_time.strftime('%H:%M')}" if s.end_time else ""
        print(f"  {s.start_time.strftime('%a %d %b %H:%M')}{end_info}{notes_info} - {s.film_title}")

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

    with open('data/prince_charles_scraped.json', 'w') as f:
        json.dump(output, f, indent=2)

    print(f"\nExported {len(output)} screenings to data/prince_charles_scraped.json")


if __name__ == '__main__':
    asyncio.run(main())
