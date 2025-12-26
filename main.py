#!/usr/bin/env python3
"""
London Cinema Listings - Terminal Interface

A simple CLI to browse cinema screenings from multiple venues.
"""

import asyncio
import sys
import math
from datetime import datetime, timedelta
from typing import Optional

import httpx

from scrapers.base import Screening, Cinema


# Cinema data with coordinates
CINEMA_INFO = {
    "rio": Cinema(
        id="rio-cinema",
        name="Rio Cinema",
        address="107 Kingsland High St",
        postcode="E8 2PB",
        website="https://riocinema.org.uk/",
        chain=None,
        lat=51.5485,
        lon=-0.0754
    ),
    "curzon": Cinema(
        id="curzon-hoxton",
        name="Curzon Hoxton",
        address="58-60 Hoxton Square",
        postcode="N1 6PB",
        website="https://www.curzon.com/venues/hoxton/",
        chain="Curzon",
        lat=51.5285,
        lon=-0.0815
    ),
    "prince_charles": Cinema(
        id="prince-charles-cinema",
        name="Prince Charles Cinema",
        address="7 Leicester Place",
        postcode="WC2H 7BY",
        website="https://princecharlescinema.com/",
        chain=None,
        lat=51.5112,
        lon=-0.1304
    ),
    "barbican": Cinema(
        id="barbican-cinema",
        name="Barbican Cinema",
        address="Silk Street",
        postcode="EC2Y 8DS",
        website="https://www.barbican.org.uk/whats-on/cinema",
        chain=None,
        lat=51.5200,
        lon=-0.0936
    ),
    "garden": Cinema(
        id="garden-cinema",
        name="The Garden Cinema",
        address="39-41 Parker Street",
        postcode="WC2B 5PQ",
        website="https://thegardencinema.co.uk",
        chain=None,
        lat=51.5160,
        lon=-0.1224
    ),
}

# Available scrapers (will be sorted by distance if postcode provided)
CINEMAS = {
    "1": ("Rio Cinema (Dalston)", "rio"),
    "2": ("Curzon Hoxton", "curzon"),
    "3": ("Prince Charles Cinema", "prince_charles"),
    "4": ("Barbican Cinema", "barbican"),
    "5": ("The Garden Cinema", "garden"),
}

# User's location (set via postcode)
user_location: Optional[tuple[float, float]] = None


def haversine_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Calculate the distance between two points in kilometers."""
    R = 6371  # Earth's radius in km

    lat1_rad = math.radians(lat1)
    lat2_rad = math.radians(lat2)
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)

    a = math.sin(dlat / 2) ** 2 + math.cos(lat1_rad) * math.cos(lat2_rad) * math.sin(dlon / 2) ** 2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))

    return R * c


async def lookup_postcode(postcode: str) -> Optional[tuple[float, float]]:
    """Look up coordinates for a UK postcode using postcodes.io API."""
    # Clean the postcode
    postcode = postcode.strip().upper().replace(" ", "")

    try:
        async with httpx.AsyncClient() as client:
            resp = await client.get(
                f"https://api.postcodes.io/postcodes/{postcode}",
                timeout=10.0
            )
            if resp.status_code == 200:
                data = resp.json()
                if data.get("status") == 200 and data.get("result"):
                    result = data["result"]
                    return (result["latitude"], result["longitude"])
    except Exception as e:
        print(f"  Error looking up postcode: {e}")

    return None


def get_distance_to_cinema(cinema_id: str) -> Optional[float]:
    """Get distance from user's location to a cinema."""
    if not user_location:
        return None

    cinema = CINEMA_INFO.get(cinema_id)
    if not cinema or not cinema.lat or not cinema.lon:
        return None

    return haversine_distance(
        user_location[0], user_location[1],
        cinema.lat, cinema.lon
    )


def get_sorted_cinemas() -> list[tuple[str, str, str, Optional[float]]]:
    """Get list of cinemas, optionally sorted by distance."""
    cinemas = []
    for key, (name, cinema_id) in CINEMAS.items():
        distance = get_distance_to_cinema(cinema_id)
        cinemas.append((key, name, cinema_id, distance))

    if user_location:
        # Sort by distance (None values at the end)
        cinemas.sort(key=lambda x: (x[3] is None, x[3] or 999))

    return cinemas


def format_distance(km: Optional[float]) -> str:
    """Format distance for display."""
    if km is None:
        return ""
    if km < 1:
        return f" ({int(km * 1000)}m)"
    return f" ({km:.1f}km)"


def print_header():
    """Print the application header."""
    print()
    print("=" * 60)
    print("  LONDON CINEMA LISTINGS")
    print("=" * 60)
    print()


def print_menu():
    """Print the cinema selection menu."""
    global user_location

    if user_location:
        print(f"  Your location: set (showing distances)")
    else:
        print("  Enter a postcode to see distances to cinemas")
    print()
    print("Select a cinema:")
    print()

    sorted_cinemas = get_sorted_cinemas()
    for i, (_, name, cinema_id, distance) in enumerate(sorted_cinemas, 1):
        dist_str = format_distance(distance)
        print(f"  [{i}] {name}{dist_str}")
    print()
    print("  [a] All cinemas (sorted by distance)")
    print("  [p] Enter postcode")
    print("  [q] Quit")
    print()


async def get_scraper(scraper_id: str):
    """Get the appropriate scraper instance."""
    if scraper_id == "rio":
        from scrapers.rio import RioScraper
        return RioScraper()
    elif scraper_id == "curzon":
        from scrapers.curzon import CurzonScraper
        return CurzonScraper(venue="hoxton")
    elif scraper_id == "prince_charles":
        from scrapers.prince_charles import PrinceCharlesScraper
        return PrinceCharlesScraper()
    elif scraper_id == "barbican":
        from scrapers.barbican import BarbicanScraper
        return BarbicanScraper()
    elif scraper_id == "garden":
        from scrapers.garden import GardenScraper
        return GardenScraper()
    return None


def filter_today(screenings: list[Screening]) -> list[Screening]:
    """Filter screenings to today only."""
    today = datetime.now().date()
    return [s for s in screenings if s.start_time.date() == today]


def filter_date_range(screenings: list[Screening], days: int) -> list[Screening]:
    """Filter screenings to the next N days."""
    today = datetime.now().date()
    end_date = today + timedelta(days=days)
    return [s for s in screenings if today <= s.start_time.date() < end_date]


def print_screenings(screenings: list[Screening], group_by_date: bool = True):
    """Print screenings in a formatted list."""
    if not screenings:
        print("  No screenings found.")
        return

    # Sort by start time
    screenings = sorted(screenings, key=lambda s: s.start_time)

    if group_by_date:
        # Group by date
        by_date = {}
        for s in screenings:
            date_key = s.start_time.strftime("%A %d %B")
            if date_key not in by_date:
                by_date[date_key] = []
            by_date[date_key].append(s)

        for date_str, day_screenings in by_date.items():
            print(f"\n  {date_str}")
            print("  " + "-" * 40)
            for s in day_screenings:
                time_str = s.start_time.strftime("%H:%M")
                end_str = f"-{s.end_time.strftime('%H:%M')}" if s.end_time else ""
                notes_str = f" [{s.notes}]" if s.notes else ""
                cinema_str = f" @ {s.cinema_name}" if len(CINEMAS) > 1 else ""
                print(f"  {time_str}{end_str}  {s.film_title}{notes_str}{cinema_str}")
    else:
        for s in screenings:
            date_str = s.start_time.strftime("%a %d %b %H:%M")
            end_str = f"-{s.end_time.strftime('%H:%M')}" if s.end_time else ""
            notes_str = f" [{s.notes}]" if s.notes else ""
            print(f"  {date_str}{end_str}  {s.film_title}{notes_str}")


async def fetch_screenings(cinema_id: str, cinema_name: str) -> list[Screening]:
    """Fetch screenings from a single cinema."""
    print(f"\n  Fetching {cinema_name}...", end=" ", flush=True)

    try:
        scraper = await get_scraper(cinema_id)
        if scraper:
            screenings = await scraper.scrape(days_ahead=7)
            print(f"found {len(screenings)} screenings")
            return screenings
        else:
            print("scraper not found")
    except Exception as e:
        print(f"error: {e}")

    return []


async def fetch_all_screenings() -> list[Screening]:
    """Fetch screenings from all cinemas."""
    all_screenings = []

    for _, (name, cinema_id) in CINEMAS.items():
        screenings = await fetch_screenings(cinema_id, name)
        all_screenings.extend(screenings)

    return all_screenings


async def show_today(cinema_id: Optional[str] = None, cinema_name: Optional[str] = None):
    """Show today's screenings."""
    if cinema_id:
        screenings = await fetch_screenings(cinema_id, cinema_name)
    else:
        screenings = await fetch_all_screenings()

    today_screenings = filter_today(screenings)

    print()
    print(f"  TODAY'S SCREENINGS ({datetime.now().strftime('%A %d %B %Y')})")
    print("=" * 60)

    if cinema_id:
        print_screenings(today_screenings, group_by_date=False)
    else:
        # Group by cinema
        by_cinema = {}
        for s in today_screenings:
            if s.cinema_name not in by_cinema:
                by_cinema[s.cinema_name] = []
            by_cinema[s.cinema_name].append(s)

        # Sort cinemas by distance if user location is set
        sorted_cinema_names = list(by_cinema.keys())
        if user_location:
            # Create distance lookup
            cinema_distances = {}
            for cinema_id, info in CINEMA_INFO.items():
                cinema_distances[info.name] = get_distance_to_cinema(cinema_id)

            sorted_cinema_names.sort(key=lambda x: (cinema_distances.get(x) is None, cinema_distances.get(x) or 999))

        for cinema in sorted_cinema_names:
            cinema_screenings = by_cinema[cinema]
            # Find distance
            dist_str = ""
            for cid, info in CINEMA_INFO.items():
                if info.name == cinema:
                    dist = get_distance_to_cinema(cid)
                    dist_str = format_distance(dist)
                    break

            print(f"\n  {cinema.upper()}{dist_str}")
            print("  " + "-" * 40)
            for s in sorted(cinema_screenings, key=lambda x: x.start_time):
                time_str = s.start_time.strftime("%H:%M")
                end_str = f"-{s.end_time.strftime('%H:%M')}" if s.end_time else ""
                notes_str = f" [{s.notes}]" if s.notes else ""
                print(f"  {time_str}{end_str}  {s.film_title}{notes_str}")


async def show_week(cinema_id: Optional[str] = None, cinema_name: Optional[str] = None):
    """Show this week's screenings."""
    if cinema_id:
        screenings = await fetch_screenings(cinema_id, cinema_name)
    else:
        screenings = await fetch_all_screenings()

    week_screenings = filter_date_range(screenings, 7)

    print()
    print("  THIS WEEK'S SCREENINGS")
    print("=" * 60)
    print_screenings(week_screenings, group_by_date=True)


async def cinema_menu(cinema_id: str, cinema_name: str):
    """Show options for a specific cinema."""
    while True:
        print()
        print(f"  {cinema_name.upper()}")
        print("-" * 40)
        print()
        print("  [1] What's on today")
        print("  [2] This week")
        print("  [b] Back to main menu")
        print()

        choice = input("  > ").strip().lower()

        if choice == "1":
            await show_today(cinema_id, cinema_name)
        elif choice == "2":
            await show_week(cinema_id, cinema_name)
        elif choice == "b":
            break
        else:
            print("  Invalid choice")


async def set_postcode():
    """Prompt user for postcode and set location."""
    global user_location

    print()
    postcode = input("  Enter your postcode: ").strip()

    if not postcode:
        print("  No postcode entered.")
        return

    print("  Looking up postcode...", end=" ", flush=True)
    coords = await lookup_postcode(postcode)

    if coords:
        user_location = coords
        print("done!")
        print(f"  Location set. Cinemas will be sorted by distance.")
    else:
        print("not found.")
        print("  Please check the postcode and try again.")


async def main():
    """Main application loop."""
    global user_location

    print_header()

    while True:
        print_menu()
        choice = input("  > ").strip().lower()

        if choice == "q":
            print("\n  Goodbye!\n")
            break
        elif choice == "p":
            await set_postcode()
        elif choice == "a":
            # All cinemas - show today's screenings
            await show_today()
        else:
            # Try to match cinema by number
            try:
                idx = int(choice)
                sorted_cinemas = get_sorted_cinemas()
                if 1 <= idx <= len(sorted_cinemas):
                    _, name, cinema_id, _ = sorted_cinemas[idx - 1]
                    await cinema_menu(cinema_id, name)
                else:
                    print("  Invalid choice. Please try again.\n")
            except ValueError:
                print("  Invalid choice. Please try again.\n")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n\n  Goodbye!\n")
        sys.exit(0)
