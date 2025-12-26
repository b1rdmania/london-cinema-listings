#!/usr/bin/env python3
"""
Capture the booking/showtime API when navigating to a film's booking page.
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
            url = response.url
            if ('json' in ct or 'boxoffice' in url.lower()) and response.status == 200:
                try:
                    body = await response.json()
                    responses.append({'url': url, 'body': body})
                except:
                    pass

        page.on('response', capture)

        # Go directly to a film page that should show showtimes
        # Using a popular current film
        film_url = "https://www.everymancinema.com/film-info/d280693-wicked/"
        print(f"Loading: {film_url}")
        await page.goto(film_url, wait_until='networkidle', timeout=60000)
        await page.wait_for_timeout(5000)

        print(f"\nCaptured {len(responses)} responses")

        # Look for showtime/session data
        for r in responses:
            url = r['url']
            body = r['body']

            # Check if this contains sessions/showtimes
            body_str = json.dumps(body)
            if any(x in body_str.lower() for x in ['session', 'showtime', 'starttime', 'screentime']):
                print(f"\n** SESSION DATA FOUND **")
                print(f"URL: {url}")
                with open('data/everyman_sessions.json', 'w') as f:
                    json.dump(body, f, indent=2)
                print(f"Saved to data/everyman_sessions.json")
                print(json.dumps(body, indent=2)[:2500])

        # Also check the page for any visible showtimes
        print("\n\nChecking page content...")
        times = await page.evaluate('''() => {
            const text = document.body.innerText;
            // Look for time patterns
            const timeMatches = text.match(/\\d{1,2}[:.:]\\d{2}\\s*(?:am|pm)?/gi) || [];
            return {
                times: timeMatches.slice(0, 20),
                hasBookButton: !!document.querySelector('[class*="book"], button[class*="Book"]')
            };
        }''')
        print(f"Times found on page: {times['times']}")
        print(f"Has book button: {times['hasBookButton']}")

        # Save screenshot
        await page.screenshot(path='data/everyman_film_page.png', full_page=True)
        print("\nScreenshot saved")

        await browser.close()


if __name__ == '__main__':
    asyncio.run(recon())
