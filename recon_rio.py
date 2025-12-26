#!/usr/bin/env python3
"""
Reconnaissance script for Rio Cinema website.
Uses Playwright to render JS and analyze page structure.
"""

import asyncio
import json
from playwright.async_api import async_playwright


async def recon_rio():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"
        )
        page = await context.new_page()

        # Capture network requests to find API endpoints
        api_requests = []

        def handle_request(request):
            url = request.url
            if any(x in url.lower() for x in ['api', 'json', 'film', 'listing', 'schedule', 'event']):
                api_requests.append({
                    'url': url,
                    'method': request.method,
                    'resource_type': request.resource_type
                })

        page.on('request', handle_request)

        print("=" * 60)
        print("RIO CINEMA RECONNAISSANCE")
        print("=" * 60)

        # Visit main page
        print("\n[1] Loading homepage...")
        await page.goto('https://riocinema.org.uk', wait_until='networkidle', timeout=30000)

        # Get page title
        title = await page.title()
        print(f"    Title: {title}")

        # Look for What's On link
        print("\n[2] Looking for navigation links...")
        nav_links = await page.evaluate('''() => {
            const links = Array.from(document.querySelectorAll('a'));
            return links.map(a => ({
                text: a.textContent.trim(),
                href: a.href
            })).filter(l => l.text && l.href);
        }''')

        whats_on_links = [l for l in nav_links if any(x in l['text'].lower() for x in ['what', 'on', 'listing', 'film', 'schedule', 'programme'])]
        print(f"    Found {len(nav_links)} total links")
        print(f"    Relevant links:")
        for link in whats_on_links[:10]:
            print(f"      - {link['text']}: {link['href']}")

        # Visit What's On page
        print("\n[3] Visiting What's On page...")
        await page.goto('https://riocinema.org.uk/whats-on/', wait_until='networkidle', timeout=30000)

        # Analyze page structure
        print("\n[4] Analyzing page structure...")

        structure = await page.evaluate('''() => {
            const result = {
                filmCards: [],
                dateElements: [],
                timeElements: [],
                possibleContainers: []
            };

            // Look for common patterns
            const selectors = [
                '.film', '.movie', '.event', '.screening', '.show',
                '[class*="film"]', '[class*="movie"]', '[class*="event"]',
                '[class*="listing"]', '[class*="screening"]',
                'article', '.card', '[class*="card"]'
            ];

            for (const sel of selectors) {
                const els = document.querySelectorAll(sel);
                if (els.length > 0) {
                    result.possibleContainers.push({
                        selector: sel,
                        count: els.length,
                        sample: els[0].className
                    });
                }
            }

            // Look for date/time patterns
            const allText = document.body.innerText;
            const dateMatches = allText.match(/\d{1,2}(?:st|nd|rd|th)?\s+(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)/gi) || [];
            result.dateExamples = dateMatches.slice(0, 5);

            const timeMatches = allText.match(/\d{1,2}[:.]\d{2}\s*(?:am|pm)?/gi) || [];
            result.timeExamples = timeMatches.slice(0, 5);

            // Get full HTML structure of first few potential film elements
            const articles = document.querySelectorAll('article');
            if (articles.length > 0) {
                result.articleSample = articles[0].outerHTML.substring(0, 2000);
            }

            // Look for any embedded JSON/data
            const scripts = document.querySelectorAll('script[type="application/json"], script[type="application/ld+json"]');
            result.jsonScripts = Array.from(scripts).map(s => s.textContent.substring(0, 500));

            return result;
        }''')

        print(f"\n    Possible film containers:")
        for container in structure.get('possibleContainers', []):
            print(f"      - {container['selector']}: {container['count']} elements (class: {container['sample']})")

        print(f"\n    Date examples found: {structure.get('dateExamples', [])}")
        print(f"    Time examples found: {structure.get('timeExamples', [])}")

        if structure.get('jsonScripts'):
            print(f"\n    Found {len(structure['jsonScripts'])} JSON script blocks")

        # Print API requests found
        print("\n[5] API/Data requests captured:")
        if api_requests:
            for req in api_requests:
                print(f"      - [{req['method']}] {req['url'][:100]}")
        else:
            print("      No obvious API endpoints detected")

        # Get a sample of the actual film listing HTML
        print("\n[6] Sample HTML structure:")
        sample = await page.evaluate('''() => {
            // Try to find the main content area
            const main = document.querySelector('main, #main, .main, [role="main"]');
            if (main) {
                return main.innerHTML.substring(0, 3000);
            }
            const body = document.body.innerHTML;
            return body.substring(0, 3000);
        }''')
        print(f"\n{sample[:2000]}...")

        # Take a screenshot for reference
        await page.screenshot(path='data/rio_whats_on.png', full_page=True)
        print("\n[7] Screenshot saved to data/rio_whats_on.png")

        await browser.close()

        print("\n" + "=" * 60)
        print("RECONNAISSANCE COMPLETE")
        print("=" * 60)


if __name__ == '__main__':
    asyncio.run(recon_rio())
