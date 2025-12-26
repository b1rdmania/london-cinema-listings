#!/usr/bin/env python3
"""
Generate screenings.json from all cinema scrapers.

This script is run by GitHub Actions daily to keep listings fresh.
Each scraper runs independently - if one fails, others still run.
"""

import asyncio
import json
import sys
from datetime import datetime
from dataclasses import asdict
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from scrapers.rio import RioScraper
from scrapers.curzon import CurzonScraper
from scrapers.prince_charles import PrinceCharlesScraper
from scrapers.barbican import BarbicanScraper
from scrapers.garden import GardenScraper
from scrapers.everyman import EverymanScraper
from scrapers.vue import VueScraper


SCRAPERS = [
    ("Rio Cinema", RioScraper()),
    ("Curzon Hoxton", CurzonScraper(venue="hoxton")),
    ("Prince Charles Cinema", PrinceCharlesScraper()),
    ("Barbican Cinema", BarbicanScraper()),
    ("Garden Cinema", GardenScraper()),
    ("Everyman Broadgate", EverymanScraper()),
    ("Vue Islington", VueScraper()),
]


async def run_scraper(name: str, scraper, days_ahead: int = 14) -> list:
    """Run a single scraper with error handling."""
    print(f"\n{'='*50}")
    print(f"Scraping {name}...")
    print('='*50)

    try:
        screenings = await scraper.scrape(days_ahead=days_ahead)
        print(f"  Found {len(screenings)} screenings")
        return screenings
    except Exception as e:
        print(f"  ERROR: {e}")
        return []


async def main():
    """Run all scrapers and generate screenings.json."""
    print("="*60)
    print("LOCAL CINEMA LISTINGS - SCRAPER")
    print(f"Started: {datetime.now().isoformat()}")
    print("="*60)

    all_screenings = []
    stats = {}

    for name, scraper in SCRAPERS:
        screenings = await run_scraper(name, scraper)
        stats[name] = len(screenings)
        all_screenings.extend(screenings)

    # Convert to JSON-serializable format
    output = []
    for s in all_screenings:
        d = asdict(s)
        d['start_time'] = s.start_time.isoformat()
        d['scraped_at'] = s.scraped_at.isoformat()
        if s.end_time:
            d['end_time'] = s.end_time.isoformat()
        output.append(d)

    # Sort by start time
    output.sort(key=lambda x: x['start_time'])

    # Build final data structure
    data = {
        "screenings": output,
        "generated_at": datetime.now().isoformat(),
        "total_screenings": len(output),
        "cinemas": len(SCRAPERS),
        "stats": stats
    }

    # Write to file
    output_path = Path(__file__).parent.parent / 'data' / 'screenings.json'
    output_path.parent.mkdir(exist_ok=True)

    with open(output_path, 'w') as f:
        json.dump(data, f, indent=2)

    # Summary
    print("\n" + "="*60)
    print("SUMMARY")
    print("="*60)
    for name, count in stats.items():
        status = "OK" if count > 0 else "FAILED"
        print(f"  {name}: {count} screenings [{status}]")
    print(f"\n  TOTAL: {len(output)} screenings")
    print(f"  Output: {output_path}")
    print(f"  Finished: {datetime.now().isoformat()}")


if __name__ == '__main__':
    asyncio.run(main())
