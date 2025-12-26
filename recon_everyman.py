#!/usr/bin/env python3
"""
Reconnaissance script for Everyman Cinema.
Check for JSON APIs, embedded data, or other structured sources.
"""

import asyncio
import json
import re
from playwright.async_api import async_playwright


async def recon_everyman():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"
        )
        page = await context.new_page()

        # Capture XHR/Fetch requests
        api_requests = []

        def handle_response(response):
            url = response.url
            content_type = response.headers.get('content-type', '')
            if 'json' in content_type or any(x in url.lower() for x in ['api', 'graphql', 'session', 'showtime', 'performance', 'film']):
                api_requests.append({
                    'url': url,
                    'status': response.status,
                    'content_type': content_type
                })

        page.on('response', handle_response)

        print("=" * 70)
        print("EVERYMAN CINEMA RECONNAISSANCE")
        print("=" * 70)

        # Visit Everyman Broadgate listings
        venue_url = "https://www.everymancinema.com/venues-list/x0898-everyman-broadgate"
        print(f"\n[1] Loading venue page: {venue_url}")

        await page.goto(venue_url, wait_until='networkidle', timeout=60000)

        title = await page.title()
        print(f"    Title: {title}")

        # Check for JSON-LD
        print("\n[2] Checking for JSON-LD structured data...")
        json_ld = await page.evaluate('''() => {
            const scripts = document.querySelectorAll('script[type="application/ld+json"]');
            return Array.from(scripts).map(s => s.textContent);
        }''')
        if json_ld:
            print(f"    Found {len(json_ld)} JSON-LD blocks")
            for i, block in enumerate(json_ld[:2]):
                try:
                    data = json.loads(block)
                    print(f"    Block {i}: {json.dumps(data, indent=2)[:500]}")
                except:
                    pass

        # Check for embedded JS data
        print("\n[3] Checking for embedded JavaScript data...")
        embedded = await page.evaluate('''() => {
            const scripts = document.querySelectorAll('script:not([src])');
            const results = [];
            for (const s of scripts) {
                const text = s.textContent;
                if (text.includes('film') || text.includes('showing') || text.includes('session') || text.includes('performance')) {
                    // Look for variable assignments
                    const matches = text.match(/(?:var|let|const|window\\.)\s*([\\w]+)\s*=\s*[\\[\\{]/g);
                    if (matches) {
                        results.push({
                            vars: matches,
                            sample: text.substring(0, 500)
                        });
                    }
                }
            }
            return results;
        }''')
        if embedded:
            print(f"    Found {len(embedded)} scripts with potential data")
            for e in embedded[:2]:
                print(f"    Variables: {e['vars']}")

        # Print captured API requests
        print(f"\n[4] API/JSON requests captured ({len(api_requests)}):")
        for req in api_requests:
            print(f"    [{req['status']}] {req['content_type'][:30] if req['content_type'] else 'N/A'}")
            print(f"        {req['url'][:120]}")

        # Look for "What's On" or film listing sections
        print("\n[5] Analyzing page structure...")
        structure = await page.evaluate('''() => {
            const result = {
                filmElements: [],
                timeElements: [],
                bookButtons: []
            };

            // Look for film cards/listings
            const selectors = [
                '[class*="film"]', '[class*="movie"]', '[class*="showing"]',
                '[class*="session"]', '[class*="screening"]', '[data-film]',
                '.card', 'article'
            ];

            for (const sel of selectors) {
                const els = document.querySelectorAll(sel);
                if (els.length > 0) {
                    result.filmElements.push({
                        selector: sel,
                        count: els.length,
                        sampleClasses: els[0].className
                    });
                }
            }

            // Look for booking/time elements
            const bookLinks = document.querySelectorAll('a[href*="book"], button[class*="book"]');
            result.bookButtons.push({count: bookLinks.length});

            return result;
        }''')

        print(f"    Film-related elements:")
        for fe in structure.get('filmElements', []):
            print(f"      {fe['selector']}: {fe['count']} (class: {fe['sampleClasses'][:50]})")

        # Take screenshot
        await page.screenshot(path='data/everyman_broadgate.png', full_page=True)
        print("\n[6] Screenshot saved to data/everyman_broadgate.png")

        # Now try to find the actual API by checking network for film data
        print("\n[7] Navigating to What's On to capture more requests...")
        whats_on_url = "https://www.everymancinema.com/venues-list/x0898-everyman-broadgate/whats-on"

        # Clear previous requests
        api_requests.clear()

        try:
            await page.goto(whats_on_url, wait_until='networkidle', timeout=60000)

            print(f"\n[8] Additional API requests from What's On page ({len(api_requests)}):")
            for req in api_requests:
                print(f"    [{req['status']}] {req['url'][:120]}")

            # Save page HTML for analysis
            html = await page.content()
            with open('data/everyman_whats_on.html', 'w') as f:
                f.write(html)
            print("\n    Saved HTML to data/everyman_whats_on.html")

        except Exception as e:
            print(f"    Error loading What's On: {e}")

        await browser.close()

        print("\n" + "=" * 70)
        print("RECONNAISSANCE COMPLETE")
        print("=" * 70)


if __name__ == '__main__':
    asyncio.run(recon_everyman())
