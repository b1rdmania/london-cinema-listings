#!/usr/bin/env python3
"""
Reconnaissance script for Prince Charles Cinema.
Explore website structure and identify data sources.
"""

import asyncio
from playwright.async_api import async_playwright


async def recon():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)"
        )
        page = await context.new_page()
        
        captured_requests = []
        captured_responses = []
        
        async def on_request(request):
            url = request.url
            if 'princecharles' in url or 'api' in url.lower():
                captured_requests.append({
                    'url': url,
                    'method': request.method,
                    'headers': dict(request.headers)
                })
        
        async def on_response(response):
            url = response.url
            content_type = response.headers.get('content-type', '')
            if 'json' in content_type or 'api' in url.lower():
                try:
                    body = await response.text()
                    captured_responses.append({
                        'url': url,
                        'status': response.status,
                        'content_type': content_type,
                        'body_preview': body[:2000] if body else None
                    })
                except:
                    pass
        
        page.on('request', on_request)
        page.on('response', on_response)
        
        print("Loading Prince Charles Cinema homepage...")
        await page.goto("https://princecharlescinema.com/", wait_until='networkidle', timeout=60000)
        await page.wait_for_timeout(3000)
        
        # Get page title
        title = await page.title()
        print(f"Page title: {title}")
        
        # Look for "What's On" or calendar link
        links = await page.query_selector_all('a')
        nav_links = []
        for link in links:
            href = await link.get_attribute('href')
            text = await link.inner_text()
            if href and text:
                text = text.strip()
                if text and len(text) < 50:
                    nav_links.append((text, href))
        
        print("\nNavigation links found:")
        for text, href in nav_links[:30]:
            print(f"  {text}: {href}")
        
        # Check for embedded JSON/data
        html = await page.content()
        print(f"\nPage HTML length: {len(html)} chars")
        
        # Look for common data patterns
        patterns = ['var films', 'var events', 'var shows', '__NEXT_DATA__', 
                    'window.__data', 'application/json', 'data-films', 'data-events']
        for pattern in patterns:
            if pattern.lower() in html.lower():
                print(f"  Found pattern: {pattern}")
        
        print(f"\nCaptured {len(captured_requests)} relevant requests")
        print(f"Captured {len(captured_responses)} JSON responses")
        
        for resp in captured_responses[:5]:
            print(f"\n  URL: {resp['url'][:100]}")
            print(f"  Status: {resp['status']}")
            if resp['body_preview']:
                print(f"  Preview: {resp['body_preview'][:500]}")
        
        # Now navigate to What's On page
        print("\n" + "="*60)
        print("Navigating to What's On page...")
        
        # Find What's On link
        whatson_url = None
        for text, href in nav_links:
            if "what" in text.lower() and "on" in text.lower():
                whatson_url = href
                break
            if "programme" in text.lower() or "schedule" in text.lower():
                whatson_url = href
                break
        
        if whatson_url:
            if not whatson_url.startswith('http'):
                whatson_url = f"https://princecharlescinema.com{whatson_url}"
            
            captured_responses.clear()
            print(f"Loading: {whatson_url}")
            await page.goto(whatson_url, wait_until='networkidle', timeout=60000)
            await page.wait_for_timeout(3000)
            
            html = await page.content()
            print(f"What's On page HTML length: {len(html)} chars")
            
            # Save for analysis
            with open('data/prince_charles_whatson.html', 'w') as f:
                f.write(html)
            print("Saved HTML to data/prince_charles_whatson.html")
            
            print(f"\nCaptured {len(captured_responses)} JSON responses on What's On page")
            for resp in captured_responses:
                print(f"\n  URL: {resp['url'][:100]}")
                if resp['body_preview']:
                    print(f"  Preview: {resp['body_preview'][:800]}")
        
        await browser.close()


if __name__ == '__main__':
    asyncio.run(recon())
