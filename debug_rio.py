#!/usr/bin/env python3
"""Debug Rio Cinema HTTP response."""

import asyncio
import httpx
from bs4 import BeautifulSoup


async def debug():
    async with httpx.AsyncClient(
        headers={
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
            "Accept-Language": "en-GB,en;q=0.5",
        },
        follow_redirects=True,
        timeout=30.0
    ) as client:
        url = "https://riocinema.org.uk/Rio.dll/WhatsOn"
        print(f"Fetching: {url}")

        response = await client.get(url)
        print(f"Status: {response.status_code}")
        print(f"Content-Type: {response.headers.get('content-type')}")
        print(f"Content length: {len(response.text)}")

        # Save raw HTML for inspection
        with open('data/rio_raw.html', 'w') as f:
            f.write(response.text)
        print("\nSaved raw HTML to data/rio_raw.html")

        # Try to parse
        soup = BeautifulSoup(response.text, 'lxml')

        # Check what we can find
        print(f"\n--- Page Analysis ---")
        print(f"Title: {soup.title.string if soup.title else 'No title'}")

        # Look for any elements with 'film' in class
        film_elements = soup.select('[class*="film"], [class*="Film"]')
        print(f"Elements with 'film' in class: {len(film_elements)}")

        # Look for cards
        cards = soup.select('.card')
        print(f"Cards: {len(cards)}")

        # Look for any div with id starting with Film_
        film_divs = soup.select('div[id^="Film_"]')
        print(f"Divs with id starting with Film_: {len(film_divs)}")

        # Sample of first 2000 chars
        print(f"\n--- First 2000 chars of HTML ---")
        print(response.text[:2000])


if __name__ == '__main__':
    asyncio.run(debug())
