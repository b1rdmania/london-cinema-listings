---
name: MultiCinemaReconAndScrapers
overview: Recon and implement scrapers for Barbican, Everyman (incl. Everyman Broadgate), Curzon Hoxton, Prince Charles Cinema, and BFI Southbank, using per-cinema modules and shared normalisation/storage.
todos: []
---

# Plan: Barbican + Everyman + 



# CurzonHoxton + PrinceCharles + BFISouthbank



## Scope

Build **per-cinema scrapers** (same interface as Rio) for:

- Barbican
- Everyman (chain approach, plus explicit venue: Everyman Broadgate)
- Curzon Hoxton
- Prince Charles Cinema
- BFI Southbank

(You clarified **“Broadgate” = Everyman Broadgate**.)

## Guiding approach (don’t guess APIs; discover them)

For each cinema we will run a short reconnaissance pass to identify the **lowest-friction source of truth**:

- **Preferred**: a stable JSON endpoint (often used by their own frontend/app)
- **Next best**: embedded structured data (JSON-LD), RSS/ICS feeds, or server-rendered HTML
- **Fallback**: Playwright-rendered DOM + extraction

We’ll codify findings in a short per-cinema note and then implement scrapers accordingly.

## Shared project structure additions

- Scraper contracts:
- [`/Users/andy/CinemaListings/scrapers/base.py`](/Users/andy/CinemaListings/scrapers/base.py)
- Per-cinema modules:
- [`/Users/andy/CinemaListings/scrapers/everyman.py`](/Users/andy/CinemaListings/scrapers/everyman.py)
- [`/Users/andy/CinemaListings/scrapers/curzon.py`](/Users/andy/CinemaListings/scrapers/curzon.py)
- [`/Users/andy/CinemaListings/scrapers/prince_charles.py`](/Users/andy/CinemaListings/scrapers/prince_charles.py)
- [`/Users/andy/CinemaListings/scrapers/bfi.py`](/Users/andy/CinemaListings/scrapers/bfi.py)
- [`/Users/andy/CinemaListings/scrapers/barbican.py`](/Users/andy/CinemaListings/scrapers/barbican.py)
- Shared utilities:
- [`/Users/andy/CinemaListings/utils/normalise.py`](/Users/andy/CinemaListings/utils/normalise.py)
- [`/Users/andy/CinemaListings/utils/datetime_parse.py`](/Users/andy/CinemaListings/utils/datetime_parse.py)
- [`/Users/andy/CinemaListings/utils/http.py`](/Users/andy/CinemaListings/utils/http.py) (headers, retries, caching)
- Cinema metadata:
- [`/Users/andy/CinemaListings/data/cinemas.json`](/Users/andy/CinemaListings/data/cinemas.json)
- Orchestration/output:
- [`/Users/andy/CinemaListings/main.py`](/Users/andy/CinemaListings/main.py)

## Reconnaissance checklist (repeat per cinema)

1. Identify the canonical **What’s On / Listings** URL(s) and whether it’s venue-specific.
2. Compare **view-source** vs rendered DOM.
3. Capture **Network/XHR/Fetch** requests and look for JSON payloads (often “performances”, “sessions”, “events”).
4. Check for:

- `application/ld+json` blocks
- ICS/RSS feeds
- sitemap sections for events
- third-party ticketing backends (common for cinemas)

5. Verify how to fetch **future dates** (URL params vs internal API date range).
6. Record “minimum viable fields” we can reliably extract: title, datetime, booking URL, venue/screen.

## Per-cinema implementation plans

### Everyman (incl. Everyman Broadgate)

- **Goal**: stable extraction for one venue (Broadgate) and optionally expand to more Everyman venues later.
- **Recon focus**:
- Find the Everyman site’s showtime data source for a specific venue.
- Determine whether the backend is a common ticketing platform (often provides JSON for sessions).
- **Scraper shape**:
- `EverymanScraper(venue_slug_or_id="broadgate", days_ahead=7)` returning `Screening` rows.
- Capture venue name/address from `data/cinemas.json`.

### Curzon Hoxton

- **Goal**: venue-specific sessions for Curzon Hoxton.
- **Recon focus**:
- Curzon sites are typically JS-heavy; locate the underlying JSON calls for showtimes.
- Confirm how venue selection is encoded (venue ID vs slug).
- **Scraper shape**:
- `CurzonScraper(venue_id="hoxton")` pulling sessions and mapping to screening schema.

### Prince Charles Cinema

- **Goal**: repertory + event screenings, often multiple formats (35mm, etc.) and special notes.
- **Recon focus**:
- Identify if their “what’s on” calendar has a feed or JSON.
- Determine if showtimes are per-film pages or calendar event pages.
- **Scraper shape**:
- Prefer event-page extraction if they expose one record per screening.
- Extract notes like “Q&A”, “Double bill”, “35mm” from titles/labels.

### BFI Southbank

- **Goal**: screenings + special events for BFI Southbank.
- **Recon focus**:
- BFI often has better structured data; check JSON-LD and any public-facing event APIs.
- Confirm if showtimes are per-programme pages or per-date schedule endpoints.
- **Scraper shape**:
- Use the most structured source available; fallback to HTML parsing with robust selectors.

### Barbican

- **Goal**: cinema screenings within the wider Barbican event ecosystem.
- **Recon focus**:
- Barbican lists many event types (music/theatre/cinema). We must filter specifically for cinema screenings.
- Look for event JSON endpoints and how cinema events are tagged.
- **Scraper shape**:
- Filter to cinema category/tag.
- Treat each screening as an event instance with datetime + booking URL.

## Data mapping + dedupe (common)

- **Stable id**: `hash(cinema_id + booking_url)` or `hash(cinema_id + provider_session_id)` when available.
- **datetime**: ISO-8601 with timezone `Europe/London`.
- **end_time**: optional; parse if present.
- **format/notes**: heuristic extraction from labels (IMAX/35mm/Q&A/Relaxed/etc.).

## Rollout order

1. Everyman Broadgate (single venue)
2. Curzon Hoxton
3. Prince Charles
4. BFI Southbank
5. Barbican

This order prioritizes likely-structured showtimes + near-term usefulness.

## Deliverables