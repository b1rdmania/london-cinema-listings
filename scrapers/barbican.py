"""
Barbican Cinema scraper.

Website: https://www.barbican.org.uk/whats-on/cinema
Platform: Spektrix ticketing system

API endpoint: spektrix.barbican.org.uk/barbicancentre/api/v3
- /events - list of all events with attributes
- /events/{id}/instances - individual showtimes for an event

Cinema events are identified by:
- name containing 'film', 'cinema'
- attribute_PrimaryArtForm = 'Film'
- Series like "Family Film Club", "Silent Film & Live Music"
"""

import asyncio
import re
from datetime import datetime, timedelta
from typing import Optional

import httpx

from .base import BaseScraper, Screening, Film, Cinema, to_london, now_london


# Barbican Cinema venue info
BARBICAN_CINEMA = Cinema(
    id="barbican-cinema",
    name="Barbican Cinema",
    address="Silk Street",
    postcode="EC2Y 8DS",
    website="https://www.barbican.org.uk/whats-on/cinema",
    chain=None,  # Arts centre
    lat=51.5200,
    lon=-0.0936
)


class BarbicanScraper(BaseScraper):
    """Scraper for Barbican Cinema using Spektrix API."""

    API_BASE = "https://spektrix.barbican.org.uk/barbicancentre/api/v3"
    WEB_BASE = "https://www.barbican.org.uk"

    def __init__(self):
        """Initialize the Barbican scraper."""
        super().__init__(BARBICAN_CINEMA)

    async def scrape(self, days_ahead: int = 30) -> list[Screening]:
        """
        Scrape all cinema screenings from Barbican.

        Note: Barbican schedules events far in advance, so days_ahead
        defaults to 30 to capture more upcoming screenings.
        """
        screenings = []
        now = now_london()
        cutoff = now + timedelta(days=days_ahead)

        async with httpx.AsyncClient(
            headers={
                'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)',
                'Accept': 'application/json',
                'Origin': 'https://www.barbican.org.uk',
                'Referer': 'https://www.barbican.org.uk/'
            },
            timeout=60.0
        ) as client:
            # Fetch cinema events
            cinema_events = await self._fetch_cinema_events(client, now, cutoff)
            print(f"Found {len(cinema_events)} cinema events")

            # Fetch instances for each event
            for event in cinema_events:
                try:
                    event_screenings = await self._fetch_event_instances(client, event, cutoff)
                    screenings.extend(event_screenings)
                    if event_screenings:
                        print(f"  {event['name']}: {len(event_screenings)} screenings")
                except Exception as e:
                    print(f"  Error fetching {event['name']}: {e}")

                await asyncio.sleep(0.1)  # Rate limiting

        return screenings

    async def get_films(self) -> list[Film]:
        """Get list of films currently showing at Barbican."""
        films = []
        now = now_london()
        cutoff = now + timedelta(days=60)

        async with httpx.AsyncClient(
            headers={
                'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)',
                'Accept': 'application/json',
            },
            timeout=60.0
        ) as client:
            cinema_events = await self._fetch_cinema_events(client, now, cutoff)

            for event in cinema_events:
                # Extract film title from event name
                title = self._extract_film_title(event.get('name', ''))
                cert = event.get('attribute_FilmCertificate', '')

                films.append(Film(
                    title=title,
                    certificate=cert if cert else None,
                    synopsis=event.get('description', '') or None,
                ))

        return films

    async def _fetch_cinema_events(
        self,
        client: httpx.AsyncClient,
        start_date: datetime,
        end_date: datetime
    ) -> list[dict]:
        """Fetch cinema events from Spektrix API."""
        cinema_events = []

        try:
            # Get all on-sale events
            resp = await client.get(
                f"{self.API_BASE}/events",
                params={
                    "$filter": "isOnSale eq true",
                    "$orderby": "firstInstanceDateTime",
                    "$top": "500"
                }
            )

            if resp.status_code != 200:
                print(f"Error fetching events: {resp.status_code}")
                return cinema_events

            events = resp.json()

            # Filter for cinema events within date range
            for event in events:
                # Check if it's a cinema event
                if not self._is_cinema_event(event):
                    continue

                # Check date range
                first_dt_str = event.get('firstInstanceDateTime', '')
                last_dt_str = event.get('lastInstanceDateTime', '')

                if not first_dt_str:
                    continue

                try:
                    first_dt = datetime.fromisoformat(first_dt_str.replace('Z', ''))
                    first_dt = to_london(first_dt)
                    last_dt = datetime.fromisoformat(last_dt_str.replace('Z', '')) if last_dt_str else first_dt
                    if last_dt_str:
                        last_dt = to_london(last_dt)

                    # Skip if entirely in the past
                    if last_dt < start_date:
                        continue

                    # Skip if starts after our cutoff
                    if first_dt > end_date:
                        continue

                    cinema_events.append(event)

                except ValueError:
                    continue

        except Exception as e:
            print(f"Error fetching cinema events: {e}")

        return cinema_events

    def _is_cinema_event(self, event: dict) -> bool:
        """Check if an event is a cinema screening."""
        name = event.get('name', '').lower()
        art_form = event.get('attribute_PrimaryArtForm', '').lower()

        # Check art form
        if art_form == 'film':
            return True

        # Check name for cinema-related keywords
        cinema_keywords = [
            'film club', 'cinema', 'screening',
            'silent film', 'animation', 'documentary'
        ]
        for keyword in cinema_keywords:
            if keyword in name:
                return True

        # Check for film certificate (indicates it's a film)
        if event.get('attribute_FilmCertificate'):
            return True

        return False

    def _extract_film_title(self, event_name: str) -> str:
        """Extract clean film title from event name."""
        # Remove common prefixes
        prefixes = [
            'Family Film Club:', 'Silent Film & Live Music:',
            'Event Cinema:', 'Pay What You Can:',
            'Magic Mondays:', 'Parent & Baby:'
        ]

        title = event_name
        for prefix in prefixes:
            if title.startswith(prefix):
                title = title[len(prefix):].strip()
                break

        # Remove certificate from end
        title = re.sub(r'\s*\([UPG0-9*]+\)\s*$', '', title)

        return title.strip()

    async def _fetch_event_instances(
        self,
        client: httpx.AsyncClient,
        event: dict,
        cutoff: datetime
    ) -> list[Screening]:
        """Fetch individual screening instances for an event."""
        screenings = []
        event_id = event.get('id', '')
        event_name = event.get('name', '')
        film_title = self._extract_film_title(event_name)
        certificate = event.get('attribute_FilmCertificate', '')

        try:
            resp = await client.get(f"{self.API_BASE}/events/{event_id}/instances")

            if resp.status_code != 200:
                return screenings

            instances = resp.json()

            for instance in instances:
                if not instance.get('isOnSale', False):
                    continue

                start_str = instance.get('start', '')
                if not start_str:
                    continue

                try:
                    start_time = datetime.fromisoformat(start_str.replace('Z', ''))
                    start_time = to_london(start_time)

                    # Skip past or too-far-future instances
                    if start_time < now_london():
                        continue
                    if start_time > cutoff:
                        continue

                    # Build booking URL
                    # Barbican uses web event pages with Spektrix widget
                    booking_url = self._build_booking_url(event_name, start_time)

                    # Build notes
                    notes_parts = []
                    if certificate:
                        notes_parts.append(certificate)

                    screening = Screening(
                        cinema_id=self.cinema.id,
                        cinema_name=self.cinema.name,
                        film_title=film_title,
                        start_time=start_time,
                        booking_url=booking_url,
                        notes='; '.join(notes_parts) if notes_parts else None
                    )

                    screenings.append(screening)

                except ValueError:
                    continue

        except Exception as e:
            print(f"Error fetching instances for {event_name}: {e}")

        return screenings

    def _build_booking_url(self, event_name: str, start_time: datetime) -> str:
        """Build the booking URL for an event."""
        # Slugify the event name
        slug = event_name.lower()
        slug = re.sub(r'[^a-z0-9]+', '-', slug)
        slug = slug.strip('-')

        # Build URL
        date_str = start_time.strftime('%Y/%m/%d')
        return f"{self.WEB_BASE}/whats-on/{date_str}/{slug}"


async def main():
    """Test the Barbican scraper."""
    import json
    from dataclasses import asdict

    print("=" * 60)
    print("BARBICAN CINEMA SCRAPER TEST")
    print("=" * 60)

    scraper = BarbicanScraper()
    screenings = await scraper.scrape(days_ahead=60)

    print(f"\nTotal screenings found: {len(screenings)}")

    # Sort by start time
    screenings.sort(key=lambda s: s.start_time)

    print("\nUpcoming screenings:")
    for s in screenings[:20]:
        notes_info = f" [{s.notes}]" if s.notes else ""
        print(f"  {s.start_time.strftime('%a %d %b %H:%M')}{notes_info} - {s.film_title}")

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

    with open('data/barbican_screenings.json', 'w') as f:
        json.dump(output, f, indent=2)

    print(f"\nExported {len(output)} screenings to data/barbican_screenings.json")


if __name__ == '__main__':
    asyncio.run(main())
