#!/usr/bin/env python3
"""
Reconnaissance script for BFI Southbank.
"""

import asyncio
from playwright.async_api import async_playwright
import json


async def recon():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)"
        )
        page = await context.new_page()
        
        api_calls = []
        
        async def on_response(response):
            url = response.url
            content_type = response.headers.get('content-type', '')
            
            # Capture API calls and JSON responses
            if 'api' in url.lower() or 'json' in content_type:
                try:
                    if response.status == 200:
                        body = await response.text()
                        api_calls.append({
                            'url': url,
                            'content_type': content_type,
                            'body_preview': body[:3000] if body else None,
                            'size': len(body) if body else 0
                        })
                except:
                    pass
        
        page.on('response', on_response)
        
        print("Loading BFI Southbank What's On page...")
        await page.goto("https://www.bfi.org.uk/bfi-southbank", wait_until='networkidle', timeout=60000)
        await page.wait_for_timeout(3000)
        
        title = await page.title()
        print(f"Page title: {title}")
        
        # Get page URL (may have redirected)
        current_url = page.url
        print(f"Current URL: {current_url}")
        
        # Look for navigation links
        links = await page.query_selector_all('a')
        nav_links = []
        for link in links:
            href = await link.get_attribute('href')
            text = await link.inner_text()
            if href and text:
                text = text.strip()
                if text and len(text) < 60:
                    nav_links.append((text, href))
        
        print("\nRelevant navigation links:")
        for text, href in nav_links[:40]:
            if any(kw in text.lower() or kw in href.lower() 
                   for kw in ['what', 'on', 'film', 'programme', 'calendar', 'schedule', 'showing']):
                print(f"  {text}: {href}")
        
        # Check for embedded data
        html = await page.content()
        print(f"\nPage HTML length: {len(html)} chars")
        
        # Look for data patterns
        patterns = ['__NEXT_DATA__', '__NUXT__', 'application/json', 'window.__data', 
                    'var films', 'var events', 'drupalSettings', 'data-drupal']
        for pattern in patterns:
            if pattern.lower() in html.lower():
                print(f"  Found pattern: {pattern}")
        
        print(f"\nCaptured {len(api_calls)} API/JSON responses:")
        for call in api_calls[:10]:
            print(f"\n  URL: {call['url'][:100]}")
            print(f"  Content-Type: {call['content_type']}")
            print(f"  Size: {call['size']} bytes")
            if call['body_preview'] and 'json' in call['content_type']:
                print(f"  Preview: {call['body_preview'][:500]}")
        
        # Now navigate to the what's on / programme page
        print("\n" + "="*60)
        print("Looking for programme/calendar page...")
        
        # Find and navigate to what's on
        whatson_url = None
        for text, href in nav_links:
            if 'what' in text.lower() and 'on' in text.lower():
                whatson_url = href
                break
            if 'programme' in text.lower() and 'southbank' in href.lower():
                whatson_url = href
                break
        
        if not whatson_url:
            # Try direct URL patterns
            for pattern in ['/whats-on', '/programme', '/calendar', '/films']:
                try:
                    test_url = f"https://www.bfi.org.uk/bfi-southbank{pattern}"
                    resp = await page.goto(test_url, wait_until='domcontentloaded', timeout=10000)
                    if resp and resp.status == 200:
                        whatson_url = test_url
                        print(f"Found working URL: {test_url}")
                        break
                except:
                    pass
        
        if whatson_url:
            if not whatson_url.startswith('http'):
                whatson_url = f"https://www.bfi.org.uk{whatson_url}"
            
            api_calls.clear()
            print(f"\nLoading: {whatson_url}")
            await page.goto(whatson_url, wait_until='networkidle', timeout=60000)
            await page.wait_for_timeout(3000)
            
            html = await page.content()
            print(f"Page HTML length: {len(html)} chars")
            
            with open('data/bfi_whatson.html', 'w') as f:
                f.write(html)
            print("Saved HTML to data/bfi_whatson.html")
            
            print(f"\nCaptured {len(api_calls)} API/JSON responses:")
            for call in api_calls:
                print(f"\n  URL: {call['url'][:120]}")
                if call['body_preview'] and 'json' in call['content_type']:
                    print(f"  Preview: {call['body_preview'][:800]}")
        
        await browser.close()


if __name__ == '__main__':
    asyncio.run(recon())
