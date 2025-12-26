#!/usr/bin/env python3
"""
Reconnaissance script for Curzon Cinema Hoxton.
"""

import asyncio
import json
from playwright.async_api import async_playwright


async def recon_curzon():
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
            if ('json' in ct or 'api' in url.lower()) and response.status == 200:
                try:
                    body = await response.json()
                    responses.append({'url': url, 'body': body})
                except:
                    pass

        page.on('response', capture)

        print("=" * 70)
        print("CURZON CINEMA RECONNAISSANCE")
        print("=" * 70)

        # Visit Curzon Hoxton
        url = "https://www.curzon.com/venues/hoxton/"
        print(f"\n[1] Loading: {url}")
        await page.goto(url, wait_until='networkidle', timeout=60000)
        await page.wait_for_timeout(3000)

        title = await page.title()
        print(f"    Title: {title}")

        # Check for JSON-LD
        print("\n[2] Checking for JSON-LD...")
        json_ld = await page.evaluate('''() => {
            const scripts = document.querySelectorAll('script[type="application/ld+json"]');
            return Array.from(scripts).map(s => s.textContent);
        }''')
        if json_ld:
            print(f"    Found {len(json_ld)} JSON-LD blocks")
            for i, block in enumerate(json_ld[:2]):
                try:
                    data = json.loads(block)
                    print(f"    Block {i}: {json.dumps(data, indent=2)[:800]}")
                except:
                    pass

        # Print captured API responses
        print(f"\n[3] Captured {len(responses)} JSON responses:")
        for r in responses:
            url = r['url']
            body = r['body']
            body_str = json.dumps(body)
            has_film = any(x in body_str.lower() for x in ['film', 'movie', 'session', 'showtime', 'screening'])
            marker = "**" if has_film else ""
            print(f"  {marker} {url[:100]}")
            if has_film:
                filename = url.split("/")[-1].split("?")[0][:30]
                with open(f'data/curzon_api_{filename}.json', 'w') as f:
                    json.dump(body, f, indent=2)

        # Check for embedded data
        print("\n[4] Checking for embedded JavaScript data...")
        embedded = await page.evaluate('''() => {
            const text = document.body.innerHTML;
            // Look for __NEXT_DATA__ or similar patterns
            const patterns = [
                /__NEXT_DATA__.*?({.*?})<\\/script>/s,
                /window\\.__PRELOAD.*?=\\s*({.*?});/s,
            ];

            for (const p of patterns) {
                const match = text.match(p);
                if (match) return match[1].substring(0, 2000);
            }
            return null;
        }''')
        if embedded:
            print(f"    Found embedded data: {embedded[:500]}")

        # Look for showtime elements
        print("\n[5] Analyzing page structure...")
        structure = await page.evaluate('''() => {
            const result = {};
            const selectors = [
                '[class*="film"]', '[class*="movie"]', '[class*="show"]',
                '[class*="session"]', '[class*="screening"]', '[class*="time"]',
                'article', '.card'
            ];

            for (const sel of selectors) {
                const els = document.querySelectorAll(sel);
                if (els.length > 0) {
                    result[sel] = {
                        count: els.length,
                        sample: els[0].className
                    };
                }
            }

            // Check for times on page
            const text = document.body.innerText;
            const times = text.match(/\\d{1,2}[:.:]\\d{2}/g) || [];
            result.times = times.slice(0, 10);

            return result;
        }''')

        for sel, info in structure.items():
            if sel != 'times':
                print(f"    {sel}: {info['count']} elements (class: {info['sample'][:50] if info.get('sample') else 'N/A'})")
        print(f"    Times found: {structure.get('times', [])}")

        # Screenshot
        await page.screenshot(path='data/curzon_hoxton.png', full_page=True)
        print("\n[6] Screenshot saved")

        # Try to find showtimes/what's on section
        print("\n[7] Looking for What's On section...")
        whats_on_link = await page.query_selector('a[href*="whats-on"], a[href*="whatson"], a[href*="films"]')
        if whats_on_link:
            href = await whats_on_link.get_attribute('href')
            print(f"    Found: {href}")

            responses.clear()
            await page.goto(href if href.startswith('http') else f"https://www.curzon.com{href}", wait_until='networkidle', timeout=60000)
            await page.wait_for_timeout(3000)

            print(f"\n[8] What's On page - {len(responses)} new JSON responses:")
            for r in responses:
                print(f"    {r['url'][:100]}")
                body_str = json.dumps(r['body'])
                if 'session' in body_str.lower() or 'showtime' in body_str.lower() or 'screening' in body_str.lower():
                    print("    ** Contains screening data! **")
                    with open('data/curzon_screenings.json', 'w') as f:
                        json.dump(r['body'], f, indent=2)
                    print(json.dumps(r['body'], indent=2)[:2000])

        await browser.close()

        print("\n" + "=" * 70)
        print("RECONNAISSANCE COMPLETE")
        print("=" * 70)


if __name__ == '__main__':
    asyncio.run(recon_curzon())
