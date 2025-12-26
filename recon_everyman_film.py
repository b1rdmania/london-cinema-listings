#!/usr/bin/env python3
"""
Reconnaissance: Capture API requests when viewing a film page on Everyman.
"""

import asyncio
import json
from playwright.async_api import async_playwright


async def recon():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)"
        )
        page = await context.new_page()

        responses = []

        async def capture(response):
            ct = response.headers.get('content-type', '')
            if 'json' in ct and response.status == 200:
                try:
                    body = await response.json()
                    responses.append({
                        'url': response.url,
                        'body': body
                    })
                except:
                    pass

        page.on('response', capture)

        # Go to film listing page
        print("Loading film listing...")
        await page.goto('https://www.everymancinema.com/film-listing/', wait_until='networkidle', timeout=60000)
        await page.wait_for_timeout(5000)

        print(f"Captured {len(responses)} JSON responses")

        # Look for session-related APIs
        for r in responses:
            url = r['url']
            if any(x in url.lower() for x in ['session', 'showtime', 'schedule', 'performance']):
                print(f"\n*** {url}")
                print(json.dumps(r['body'], indent=2)[:1500])

        # Also check for showtimes in the movies data
        for r in responses:
            if 'movies' in r['url']:
                body = r['body']
                if isinstance(body, list) and body:
                    movie = body[0]
                    print(f"\nMovie data sample (first item):")
                    print(f"Keys: {list(movie.keys())}")
                    # Check for showtimes
                    if 'showtimes' in movie or 'sessions' in movie or 'performances' in movie:
                        print("  -> Has showtimes!")
                        print(json.dumps(movie, indent=2)[:2000])
                    break

        # Try clicking on a specific film to see booking options
        print("\n\nLooking for film cards...")
        films = await page.query_selector_all('[class*="MovieCard"], [class*="movie-card"], article')
        print(f"Found {len(films)} film elements")

        if films:
            # Click first film
            responses.clear()
            try:
                await films[0].click()
                await page.wait_for_timeout(5000)
                print(f"\nAfter clicking film, captured {len(responses)} new JSON responses")
                for r in responses:
                    print(f"  {r['url'][:80]}")
            except Exception as e:
                print(f"Click error: {e}")

        await browser.close()


if __name__ == '__main__':
    asyncio.run(recon())
