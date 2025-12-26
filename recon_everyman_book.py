#!/usr/bin/env python3
"""
Capture showtimes API when navigating to book tickets for a specific film at a venue.
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
            url = response.url
            ct = response.headers.get('content-type', '')
            if ('json' in ct or 'boxoffice' in url.lower() or 'session' in url.lower() or 'showtime' in url.lower()) and response.status == 200:
                try:
                    body = await response.json()
                    responses.append({'url': url, 'body': body})
                except:
                    pass

        page.on('response', capture)

        # Try to find a working film URL from the data we have
        # Check the allMovie nodes we captured
        films_url = "https://www.everymancinema.com/film-listing/d280693-wicked/"
        print(f"Trying: {films_url}")
        await page.goto(films_url, wait_until='networkidle', timeout=60000)

        # Check URL - did we get redirected or 404?
        current_url = page.url
        print(f"Current URL: {current_url}")

        # Let's try navigating from homepage to a film
        print("\nNavigating to homepage...")
        responses.clear()
        await page.goto("https://www.everymancinema.com/", wait_until='networkidle', timeout=60000)
        await page.wait_for_timeout(3000)

        # Look for a "Book Now" or film link
        book_link = await page.query_selector('a[href*="film-listing"]:not([href="/film-listing/"])')
        if book_link:
            href = await book_link.get_attribute('href')
            print(f"Found film link: {href}")
            await book_link.click()
            await page.wait_for_load_state('networkidle')
            await page.wait_for_timeout(3000)

        print(f"\nCaptured {len(responses)} JSON responses")
        for r in responses:
            url = r['url']
            body_str = json.dumps(r['body'])
            if any(x in body_str.lower() for x in ['starttime', 'showtime', 'session', 'performance', 'startdate']):
                print(f"\n** FOUND: {url[:100]}")
                with open('data/everyman_session_data.json', 'w') as f:
                    json.dump(r['body'], f, indent=2)
                print(json.dumps(r['body'], indent=2)[:2000])

        # Check for iframes or external booking widgets
        print("\n\nChecking for iframes...")
        iframes = await page.query_selector_all('iframe')
        print(f"Found {len(iframes)} iframes")
        for iframe in iframes:
            src = await iframe.get_attribute('src')
            if src:
                print(f"  - {src[:100]}")

        # Save screenshot
        await page.screenshot(path='data/everyman_book_page.png', full_page=True)

        await browser.close()


if __name__ == '__main__':
    asyncio.run(recon())
