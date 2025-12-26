#!/usr/bin/env python3
"""
Deep reconnaissance for Everyman showtimes API.
Navigate to venue page and capture all network requests.
"""

import asyncio
import json
from playwright.async_api import async_playwright


async def recon_everyman_api():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"
        )
        page = await context.new_page()

        # Capture ALL responses with their bodies
        api_responses = []

        async def handle_response(response):
            url = response.url
            content_type = response.headers.get('content-type', '')

            # Capture JSON responses
            if 'json' in content_type and response.status == 200:
                try:
                    body = await response.json()
                    api_responses.append({
                        'url': url,
                        'body': body
                    })
                except:
                    pass

        page.on('response', handle_response)

        print("=" * 70)
        print("EVERYMAN API DEEP RECONNAISSANCE")
        print("=" * 70)

        # Navigate to venue showtimes page
        url = "https://www.everymancinema.com/venues-list/x11nt-everyman-broadgate/"
        print(f"\n[1] Loading: {url}")
        await page.goto(url, wait_until='networkidle', timeout=60000)
        await page.wait_for_timeout(3000)

        # Look for a "What's On" or showtimes section
        print("\n[2] Looking for showtimes links...")
        links = await page.evaluate('''() => {
            return Array.from(document.querySelectorAll('a')).map(a => ({
                text: a.textContent.trim(),
                href: a.href
            })).filter(l => l.text.toLowerCase().includes('what') ||
                           l.text.toLowerCase().includes('film') ||
                           l.text.toLowerCase().includes('show') ||
                           l.text.toLowerCase().includes('book'));
        }''')

        for link in links[:10]:
            print(f"  {link['text'][:30]}: {link['href'][:60]}")

        # Click on "What's On" or similar if exists
        whats_on = [l for l in links if "what's on" in l['text'].lower() or 'films' in l['text'].lower()]
        if whats_on:
            print(f"\n[3] Clicking: {whats_on[0]['text']}")
            api_responses.clear()
            await page.click(f'a[href="{whats_on[0]["href"]}"]')
            await page.wait_for_load_state('networkidle')
            await page.wait_for_timeout(3000)

        # Now check captured API responses
        print(f"\n[4] Captured {len(api_responses)} JSON responses:")
        for resp in api_responses:
            url = resp['url']
            body = resp['body']
            size = len(json.dumps(body)) if body else 0
            print(f"\n  URL: {url[:100]}")
            print(f"  Size: {size} bytes")

            # Look for showtime-related data
            body_str = json.dumps(body).lower()
            if any(x in body_str for x in ['showtime', 'session', 'screening', 'performance', 'schedule']):
                print(f"  ** Contains showtime-related data **")
                # Save this response
                filename = url.split('/')[-1].split('?')[0][:30] or 'response'
                with open(f'data/everyman_api_{filename}.json', 'w') as f:
                    json.dump(body, f, indent=2)
                print(f"  Saved to data/everyman_api_{filename}.json")

        # Take screenshot
        await page.screenshot(path='data/everyman_broadgate_showtimes.png', full_page=True)

        # Also check if there's any inline script data
        print("\n[5] Checking for inline data...")
        inline = await page.evaluate('''() => {
            const scripts = document.querySelectorAll('script:not([src])');
            for (const s of scripts) {
                if (s.textContent.includes('session') || s.textContent.includes('showtime')) {
                    return s.textContent.substring(0, 2000);
                }
            }
            return null;
        }''')

        if inline:
            print(f"  Found inline script with session/showtime data")
            print(inline[:500])

        await browser.close()


if __name__ == '__main__':
    asyncio.run(recon_everyman_api())
