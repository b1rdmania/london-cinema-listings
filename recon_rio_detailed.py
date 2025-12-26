#!/usr/bin/env python3
"""
Detailed extraction of Rio Cinema film card structure.
"""

import asyncio
import json
from playwright.async_api import async_playwright


async def extract_rio_structure():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()

        await page.goto('https://riocinema.org.uk/Rio.dll/WhatsOn', wait_until='networkidle', timeout=30000)

        # Extract detailed structure of film cards
        data = await page.evaluate('''() => {
            const results = {
                featuredFilms: [],
                upcomingShows: [],
                specialEvents: []
            };

            // Get all cards/film elements
            const cards = document.querySelectorAll('.card');

            cards.forEach((card, idx) => {
                const filmData = {
                    index: idx,
                    classes: card.className,
                    title: null,
                    dates: [],
                    times: [],
                    link: null,
                    image: null,
                    htmlSample: card.outerHTML.substring(0, 1500)
                };

                // Extract title
                const titleEl = card.querySelector('.film-title, h2, h3, .title');
                if (titleEl) {
                    filmData.title = titleEl.textContent.trim();
                }

                // Extract links
                const linkEl = card.querySelector('a[href*="WhatsOn"]');
                if (linkEl) {
                    filmData.link = linkEl.href;
                }

                // Extract image
                const imgEl = card.querySelector('img');
                if (imgEl) {
                    filmData.image = imgEl.src;
                }

                // Look for date/time info
                const textContent = card.textContent;

                // Date patterns
                const dateMatches = textContent.match(/\\d{1,2}(?:st|nd|rd|th)?\\s*(?:JAN|FEB|MAR|APR|MAY|JUN|JUL|AUG|SEP|OCT|NOV|DEC)/gi);
                if (dateMatches) {
                    filmData.dates = dateMatches;
                }

                // Time patterns
                const timeMatches = textContent.match(/\\d{1,2}[:.:]\\d{2}/g);
                if (timeMatches) {
                    filmData.times = timeMatches;
                }

                results.upcomingShows.push(filmData);
            });

            // Also look for any film-specific elements
            const filmTitles = document.querySelectorAll('.film-title');
            results.filmTitleElements = Array.from(filmTitles).slice(0, 10).map(el => ({
                text: el.textContent.trim(),
                parent: el.parentElement ? el.parentElement.className : null,
                grandparent: el.parentElement?.parentElement ? el.parentElement.parentElement.className : null
            }));

            // Look for screening time elements
            const screeningEls = document.querySelectorAll('[class*="screening"], [class*="time"], [class*="session"]');
            results.screeningElements = Array.from(screeningEls).slice(0, 5).map(el => ({
                classes: el.className,
                text: el.textContent.trim().substring(0, 200)
            }));

            return results;
        }''')

        print("=" * 70)
        print("RIO CINEMA - DETAILED STRUCTURE ANALYSIS")
        print("=" * 70)

        print(f"\n[CARDS FOUND]: {len(data['upcomingShows'])}")

        print("\n" + "-" * 70)
        print("SAMPLE FILM CARDS (first 3):")
        print("-" * 70)

        for card in data['upcomingShows'][:3]:
            print(f"\n  Card #{card['index']}:")
            print(f"    Classes: {card['classes'][:80]}...")
            print(f"    Title: {card['title']}")
            print(f"    Link: {card['link']}")
            print(f"    Dates: {card['dates']}")
            print(f"    Times: {card['times']}")
            print(f"\n    HTML Sample:\n{card['htmlSample'][:800]}")
            print("    " + "-" * 50)

        print("\n" + "-" * 70)
        print("FILM TITLE ELEMENTS:")
        print("-" * 70)
        for ft in data.get('filmTitleElements', []):
            print(f"  '{ft['text']}' - parent: {ft['parent']}")

        print("\n" + "-" * 70)
        print("SCREENING/TIME ELEMENTS:")
        print("-" * 70)
        for se in data.get('screeningElements', []):
            print(f"  Class: {se['classes']}")
            print(f"  Text: {se['text'][:100]}")
            print()

        await browser.close()


if __name__ == '__main__':
    asyncio.run(extract_rio_structure())
