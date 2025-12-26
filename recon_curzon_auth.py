#!/usr/bin/env python3
"""
Capture Curzon API auth token from browser session.
"""

import asyncio
import json
from playwright.async_api import async_playwright


async def capture_auth():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)"
        )
        page = await context.new_page()

        auth_headers = {}
        api_data = {}

        async def capture(response):
            url = response.url
            if 'vwc.curzon.com' in url and response.status == 200:
                # Capture the request headers
                request = response.request
                headers = request.headers
                if 'authorization' in headers:
                    auth_headers['authorization'] = headers['authorization']
                if 'x-client-id' in headers:
                    auth_headers['x-client-id'] = headers['x-client-id']

                # Capture response
                try:
                    body = await response.json()
                    endpoint = url.split('ocapi/v1/')[-1].split('?')[0]
                    api_data[endpoint] = body
                except:
                    pass

        page.on('response', capture)

        print("Loading Curzon Hoxton page...")
        await page.goto("https://www.curzon.com/venues/hoxton/", wait_until='networkidle', timeout=60000)
        await page.wait_for_timeout(5000)

        print(f"\nCaptured auth headers: {list(auth_headers.keys())}")
        for k, v in auth_headers.items():
            print(f"  {k}: {v[:80]}...")

        print(f"\nCaptured API data for: {list(api_data.keys())}")

        # Save the auth token
        if auth_headers:
            with open('data/curzon_auth.json', 'w') as f:
                json.dump(auth_headers, f, indent=2)
            print("\nSaved auth headers to data/curzon_auth.json")

        # Save showtimes data
        for endpoint, data in api_data.items():
            if 'showtime' in endpoint.lower():
                with open(f'data/curzon_{endpoint.replace("/", "_")}.json', 'w') as f:
                    json.dump(data, f, indent=2)
                print(f"\nSaved {endpoint}")
                if 'showtimes' in data:
                    print(f"  -> {len(data['showtimes'])} showtimes")
                    if data['showtimes']:
                        print(f"  First showtime: {json.dumps(data['showtimes'][0], indent=2)[:1000]}")

        await browser.close()


if __name__ == '__main__':
    asyncio.run(capture_auth())
