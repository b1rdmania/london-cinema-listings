"""
Rio Cinema scraper.

Website: https://riocinema.org.uk
Platform: Savoy Systems ticketing (Rio.dll routes)

Data source: Embedded JSON in the listings page (var Events = {...})
This contains all films and performances in a single request - no need for
multiple page loads or JavaScript rendering.

Performance flags:
  QA = Q&A after
  HoH = Hard of Hearing
  RS = Relaxed Screening
  CB = Carers & Babies
  SP = Special Performance
  PP = Preview Performance
  FF = Family Friendly
"""

import asyncio
import html
import json
import re
from datetime import datetime, timedelta
from typing import Optional
import httpx

from .base import BaseScraper, Screening, Film, Cinema


# Rio Cinema venue info
RIO_CINEMA = Cinema(
    id="rio",
    name="Rio Cinema",
    address="107 Kingsland High Street",
    postcode="E8 2PB",
    website="https://riocinema.org.uk",
    chain="Independent",
    lat=51.5489,
    lon=-0.0758
)


class RioScraper(BaseScraper):
    """Scraper for Rio Cinema Dalston using embedded JSON data."""

    BASE_URL = "https://riocinema.org.uk"
    LISTINGS_URL = f"{BASE_URL}/Rio.dll/WhatsOn"

    # Map performance flags to human-readable notes
    FLAG_MAP = {
        'QA': 'Q&A after',
        'HoH': 'Hard of Hearing',
        'RS': 'Relaxed Screening',
        'CB': 'Carers & Babies',
        'SP': 'Special Performance',
        'PP': 'Preview',
        'FF': 'Family Friendly',
        'NoAds': 'No Ads',
    }

    def __init__(self):
        super().__init__(RIO_CINEMA)

    async def scrape(self, days_ahead: int = 14) -> list[Screening]:
        """Scrape all screenings from Rio Cinema."""
        screenings = []

        async with httpx.AsyncClient(
            headers={
                "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
                "Accept": "text/html,application/xhtml+xml",
            },
            follow_redirects=True,
            timeout=30.0
        ) as client:
            # Fetch listings page
            response = await client.get(self.LISTINGS_URL)
            page_html = response.text

            # Extract embedded JSON
            events_data = self._extract_events_json(page_html)
            if not events_data:
                print("Warning: Could not extract Events JSON from page")
                return screenings

            events = events_data.get('Events', [])
            print(f"Found {len(events)} films in embedded JSON")

            cutoff_date = datetime.now() + timedelta(days=days_ahead)

            for event in events:
                try:
                    film_screenings = self._parse_event(event, cutoff_date)
                    screenings.extend(film_screenings)
                    if film_screenings:
                        title = html.unescape(event.get('Title', 'Unknown'))
                        print(f"  {title}: {len(film_screenings)} screenings")
                except Exception as e:
                    print(f"  Error parsing {event.get('Title', 'Unknown')}: {e}")

        return screenings

    async def get_films(self) -> list[Film]:
        """Get list of films currently showing at Rio."""
        films = []

        async with httpx.AsyncClient(
            headers={"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)"},
            follow_redirects=True,
            timeout=30.0
        ) as client:
            response = await client.get(self.LISTINGS_URL)
            events_data = self._extract_events_json(response.text)

            if not events_data:
                return films

            for event in events_data.get('Events', []):
                certificate = self._extract_certificate(event.get('Rating', ''))
                films.append(Film(
                    title=html.unescape(event.get('Title', '')),
                    year=int(event.get('Year')) if event.get('Year') else None,
                    director=event.get('Director') or None,
                    runtime_mins=event.get('RunningTime') or None,
                    certificate=certificate,
                    synopsis=event.get('Synopsis') or None,
                ))

        return films

    def _extract_events_json(self, page_html: str) -> Optional[dict]:
        """Extract the embedded Events JSON from the page HTML."""
        # Find 'var Events = {...}'
        start_marker = 'var Events'
        start_idx = page_html.find(start_marker)
        if start_idx == -1:
            return None

        # Find the opening brace
        brace_idx = page_html.find('{', start_idx)
        if brace_idx == -1:
            return None

        # Find matching closing brace by counting depth
        depth = 0
        end_idx = brace_idx
        for i, c in enumerate(page_html[brace_idx:], brace_idx):
            if c == '{':
                depth += 1
            elif c == '}':
                depth -= 1
                if depth == 0:
                    end_idx = i + 1
                    break

        json_str = page_html[brace_idx:end_idx]

        try:
            return json.loads(json_str)
        except json.JSONDecodeError:
            return None

    def _parse_event(self, event: dict, cutoff_date: datetime) -> list[Screening]:
        """Parse an event and its performances into Screening objects."""
        screenings = []
        film_title = html.unescape(event.get('Title', ''))
        film_url = event.get('URL', '')

        for perf in event.get('Performances', []):
            try:
                # Skip sold out or not open for sale
                if not perf.get('IsOpenForSale', True):
                    continue

                # Parse date and time
                start_date = perf.get('StartDate')  # "2025-12-27"
                start_time = perf.get('StartTime')  # "1430"

                if not (start_date and start_time):
                    continue

                # Parse datetime
                dt = datetime.strptime(f"{start_date} {start_time}", "%Y-%m-%d %H%M")

                # Skip if past cutoff
                if dt > cutoff_date:
                    continue

                # Build booking URL
                perf_url = perf.get('URL', '')
                if perf_url:
                    booking_url = f"{self.BASE_URL}/Rio.dll/{perf_url}"
                else:
                    booking_url = film_url

                # Extract notes from flags
                notes = self._extract_notes(perf)

                # Get screen name
                screen = perf.get('AuditoriumName') or None

                screening = Screening(
                    cinema_id=self.cinema.id,
                    cinema_name=self.cinema.name,
                    film_title=film_title,
                    start_time=dt,
                    booking_url=booking_url,
                    screen=screen,
                    notes=notes,
                )

                screenings.append(screening)

            except Exception:
                continue

        return screenings

    def _extract_notes(self, perf: dict) -> Optional[str]:
        """Extract human-readable notes from performance flags."""
        notes = []

        for flag, label in self.FLAG_MAP.items():
            if perf.get(flag) == 'Y':
                notes.append(label)

        # Also include any explicit notes
        if perf.get('Notes'):
            notes.append(perf['Notes'])

        return '; '.join(notes) if notes else None

    def _extract_certificate(self, rating_html: str) -> Optional[str]:
        """Extract BBFC certificate from rating HTML."""
        match = re.search(r'BBFC Rating:\s*\((\w+)\)', rating_html)
        return match.group(1) if match else None


async def main():
    """Test the Rio scraper."""
    from dataclasses import asdict

    print("=" * 60)
    print("RIO CINEMA SCRAPER TEST")
    print("=" * 60)

    scraper = RioScraper()
    screenings = await scraper.scrape(days_ahead=14)

    # Deduplicate by screening ID
    seen = set()
    unique_screenings = []
    for s in screenings:
        if s.id not in seen:
            seen.add(s.id)
            unique_screenings.append(s)

    print(f"\nTotal screenings found: {len(screenings)}")
    print(f"After deduplication: {len(unique_screenings)}")

    # Sort by datetime
    unique_screenings.sort(key=lambda s: s.start_time)

    print("\nUpcoming screenings:")
    for s in unique_screenings[:20]:
        screen_info = f" [{s.screen}]" if s.screen else ""
        notes_info = f" ({s.notes})" if s.notes else ""
        print(f"  {s.start_time.strftime('%a %d %b %H:%M')}{screen_info} - {s.film_title}{notes_info}")

    # Group by film
    films = {}
    for s in unique_screenings:
        if s.film_title not in films:
            films[s.film_title] = []
        films[s.film_title].append(s)

    print(f"\n{len(films)} unique films with screenings:")
    for title, shows in sorted(films.items()):
        print(f"  {title}: {len(shows)} screenings")

    # Export to JSON
    output = []
    for s in unique_screenings:
        d = asdict(s)
        d['start_time'] = s.start_time.isoformat()
        d['scraped_at'] = s.scraped_at.isoformat()
        if s.end_time:
            d['end_time'] = s.end_time.isoformat()
        output.append(d)

    with open('data/rio_screenings.json', 'w') as f:
        json.dump(output, f, indent=2)

    print(f"\nExported {len(output)} screenings to data/rio_screenings.json")


if __name__ == '__main__':
    asyncio.run(main())
