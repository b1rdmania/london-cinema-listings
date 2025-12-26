#!/usr/bin/env python3
"""
Extract screening details from a Rio Cinema film detail page.
"""

import asyncio
from playwright.async_api import async_playwright


async def extract_film_detail():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()

        # Visit a specific film page (Zootropolis 2)
        url = 'https://riocinema.org.uk/Rio.dll/WhatsOn?f=1913423'
        print(f"Fetching: {url}")

        await page.goto(url, wait_until='domcontentloaded', timeout=60000)
        await page.wait_for_timeout(3000)  # Wait for JS to render

        # Take screenshot
        await page.screenshot(path='data/rio_film_detail.png', full_page=True)

        # Extract screening data
        data = await page.evaluate('''() => {
            const result = {
                title: null,
                synopsis: null,
                runtime: null,
                director: null,
                screenings: [],
                rawHTML: null
            };

            // Get title
            const titleEl = document.querySelector('h1, .film-title, .title');
            if (titleEl) result.title = titleEl.textContent.trim();

            // Get synopsis
            const synopsisEl = document.querySelector('.synopsis, .description, [class*="synopsis"]');
            if (synopsisEl) result.synopsis = synopsisEl.textContent.trim().substring(0, 300);

            // Look for screening/showtime elements
            const selectors = [
                '.screening', '.showtime', '.session', '.performance',
                '[class*="screening"]', '[class*="showtime"]', '[class*="session"]',
                '[class*="time"]', '.book-button', '[class*="book"]',
                'button', '.btn'
            ];

            for (const sel of selectors) {
                const els = document.querySelectorAll(sel);
                if (els.length > 0) {
                    result.screenings.push({
                        selector: sel,
                        count: els.length,
                        samples: Array.from(els).slice(0, 3).map(el => ({
                            text: el.textContent.trim().substring(0, 100),
                            classes: el.className,
                            html: el.outerHTML.substring(0, 500)
                        }))
                    });
                }
            }

            // Look for date/time patterns in page
            const bodyText = document.body.innerText;
            const dateTimeMatches = bodyText.match(/\\d{1,2}(?:st|nd|rd|th)?\\s+(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)(?:uary|ruary|ch|il|e|y|ust|ember|ober|ember)?\\s*(?:20\\d{2})?\\s*(?:at)?\\s*\\d{1,2}[:.:]\\d{2}(?:\\s*(?:am|pm))?/gi);
            result.dateTimePatterns = dateTimeMatches ? dateTimeMatches.slice(0, 10) : [];

            // Get main content area HTML
            const mainContent = document.querySelector('main, #main, .main-content, .film-detail');
            if (mainContent) {
                result.rawHTML = mainContent.outerHTML.substring(0, 5000);
            } else {
                result.rawHTML = document.body.innerHTML.substring(0, 5000);
            }

            // Look for booking links specifically
            const bookingLinks = document.querySelectorAll('a[href*="Booking"], a[href*="book"]');
            result.bookingLinks = Array.from(bookingLinks).map(a => ({
                text: a.textContent.trim(),
                href: a.href
            }));

            return result;
        }''')

        print("\n" + "=" * 70)
        print("FILM DETAIL PAGE ANALYSIS")
        print("=" * 70)

        print(f"\nTitle: {data['title']}")
        print(f"Synopsis: {data['synopsis']}")
        print(f"\nDate/Time patterns found: {data['dateTimePatterns']}")

        print(f"\nBooking links ({len(data['bookingLinks'])}):")
        for link in data['bookingLinks'][:10]:
            print(f"  - {link['text'][:50]}: {link['href'][:80]}")

        print(f"\nScreening elements found:")
        for group in data['screenings']:
            print(f"\n  Selector: {group['selector']} ({group['count']} elements)")
            for sample in group['samples']:
                print(f"    Text: {sample['text'][:60]}")
                print(f"    Classes: {sample['classes']}")

        print("\n" + "-" * 70)
        print("RAW HTML SAMPLE:")
        print("-" * 70)
        print(data['rawHTML'][:3000])

        await browser.close()


if __name__ == '__main__':
    asyncio.run(extract_film_detail())
