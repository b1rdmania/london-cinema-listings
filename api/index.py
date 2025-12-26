"""
FastAPI web API for London Cinema Listings.
Deployed to Vercel serverless functions.
"""

from datetime import datetime
from typing import Optional
import json
import os

from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse

app = FastAPI(
    title="London Cinema Listings API",
    description="Aggregated cinema listings from London's best independent cinemas",
    version="0.1.0"
)

# Enable CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Cinema info
CINEMAS = {
    "rio": {
        "id": "rio",
        "name": "Rio Cinema",
        "area": "Dalston",
        "address": "107 Kingsland High St, London E8 2PB",
        "lat": 51.5485,
        "lon": -0.0754,
        "website": "https://riocinema.org.uk",
        "screens": 1,
        "seats": 400,
        "sound": "Dolby 7.1",
        "bar": True,
        "food": "Snacks, popcorn",
        "notes": "Grade II listed Art Deco building, opened 1915"
    },
    "curzon-hoxton": {
        "id": "curzon-hoxton",
        "name": "Curzon Hoxton",
        "area": "Hoxton",
        "address": "58-60 Hoxton Square, London N1 6PB",
        "lat": 51.5285,
        "lon": -0.0815,
        "website": "https://www.curzon.com/venues/hoxton/",
        "screens": 2,
        "seats": 150,
        "sound": "Dolby Atmos",
        "bar": True,
        "food": "Hot food, snacks, coffee",
        "notes": "Part of Curzon chain, screens 1-2"
    },
    "prince-charles-cinema": {
        "id": "prince-charles-cinema",
        "name": "Prince Charles Cinema",
        "area": "Leicester Square",
        "address": "7 Leicester Place, London WC2H 7BY",
        "lat": 51.5112,
        "lon": -0.1304,
        "website": "https://princecharlescinema.com/",
        "screens": 2,
        "seats": 488,
        "sound": "Dolby 7.1",
        "bar": False,
        "food": "Snacks, pick & mix",
        "notes": "Famous for sing-alongs, double bills, cult films"
    },
    "barbican-cinema": {
        "id": "barbican-cinema",
        "name": "Barbican Cinema",
        "area": "Barbican",
        "address": "Silk Street, London EC2Y 8DS",
        "lat": 51.5200,
        "lon": -0.0936,
        "website": "https://www.barbican.org.uk/whats-on/cinema",
        "screens": 3,
        "seats": 288,
        "sound": "Dolby Atmos (Screen 1)",
        "bar": True,
        "food": "Restaurant, cafe, bars",
        "notes": "Part of Barbican Centre arts complex"
    },
    "garden-cinema": {
        "id": "garden-cinema",
        "name": "The Garden Cinema",
        "area": "Covent Garden",
        "address": "39-41 Parker Street, London WC2B 5PQ",
        "lat": 51.5160,
        "lon": -0.1224,
        "website": "https://thegardencinema.co.uk",
        "screens": 2,
        "seats": 94,
        "sound": "Dolby 7.1",
        "bar": True,
        "food": "Restaurant, bar, snacks",
        "notes": "Boutique cinema with restaurant, 16mm projection"
    }
}

def load_screenings():
    """Load screenings from static JSON file."""
    data_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'data', 'screenings.json')
    try:
        with open(data_path, 'r') as f:
            return json.load(f)
    except FileNotFoundError:
        return {"screenings": [], "generated_at": None, "total_screenings": 0}


@app.get("/api/cinemas")
async def list_cinemas():
    """List all available cinemas."""
    return {"cinemas": list(CINEMAS.values())}


@app.get("/api/screenings")
async def get_screenings(
    cinema: Optional[str] = Query(None, description="Filter by cinema ID"),
    date: Optional[str] = Query(None, description="Filter by date (YYYY-MM-DD)")
):
    """Get upcoming screenings."""
    data = load_screenings()
    screenings = data.get('screenings', [])

    # Filter by cinema
    if cinema:
        screenings = [s for s in screenings if s.get('cinema_id') == cinema]

    # Filter by date
    if date:
        screenings = [s for s in screenings if s.get('start_time', '').startswith(date)]

    return {
        "screenings": screenings,
        "total": len(screenings),
        "generated_at": data.get('generated_at')
    }


@app.get("/api/screenings/today")
async def get_today_screenings(cinema: Optional[str] = None):
    """Get today's screenings."""
    today = datetime.now().strftime("%Y-%m-%d")
    return await get_screenings(cinema=cinema, date=today)


@app.get("/api/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy", "timestamp": datetime.now().isoformat()}


# Main HTML frontend
@app.get("/", response_class=HTMLResponse)
async def web_app():
    """Main web frontend."""
    return HTML_TEMPLATE


HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>London Cinema Listings</title>
    <style>
        * { box-sizing: border-box; margin: 0; padding: 0; }

        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', sans-serif;
            background: #0d0d0d;
            color: #e5e5e5;
            min-height: 100vh;
            line-height: 1.5;
        }

        .container {
            max-width: 900px;
            margin: 0 auto;
            padding: 2rem 1rem;
        }

        header {
            text-align: center;
            margin-bottom: 2rem;
            padding-bottom: 1.5rem;
            border-bottom: 1px solid #333;
        }

        h1 {
            font-size: 1.75rem;
            font-weight: 600;
            color: #fff;
            margin-bottom: 0.5rem;
        }

        .subtitle {
            color: #888;
            font-size: 0.9rem;
        }

        .filters {
            display: flex;
            gap: 0.75rem;
            margin-bottom: 1.5rem;
            flex-wrap: wrap;
        }

        .filter-btn {
            padding: 0.5rem 1rem;
            background: #1a1a1a;
            border: 1px solid #333;
            border-radius: 6px;
            color: #ccc;
            font-size: 0.875rem;
            cursor: pointer;
            transition: all 0.15s;
        }

        .filter-btn:hover {
            background: #252525;
            border-color: #444;
        }

        .filter-btn.active {
            background: #2563eb;
            border-color: #2563eb;
            color: #fff;
        }

        .date-nav {
            display: flex;
            gap: 0.5rem;
            margin-bottom: 1.5rem;
            overflow-x: auto;
            padding-bottom: 0.5rem;
            justify-content: center;
        }

        .date-btn {
            padding: 0.5rem 0.75rem;
            background: #1a1a1a;
            border: 1px solid #333;
            border-radius: 6px;
            color: #aaa;
            font-size: 0.8rem;
            cursor: pointer;
            white-space: nowrap;
            transition: all 0.15s;
        }

        .date-btn:hover {
            background: #252525;
        }

        .date-btn.active {
            background: #1e3a5f;
            border-color: #2563eb;
            color: #fff;
        }

        .screening-group {
            margin-bottom: 2rem;
        }

        .group-header {
            font-size: 0.75rem;
            font-weight: 600;
            color: #888;
            text-transform: uppercase;
            letter-spacing: 0.05em;
            margin-bottom: 0.75rem;
            padding-bottom: 0.5rem;
            border-bottom: 1px solid #222;
            display: flex;
            align-items: center;
            gap: 0.5rem;
        }

        .info-link, .imdb-link {
            font-size: 0.7rem;
            color: #2563eb;
            cursor: pointer;
            text-transform: none;
            letter-spacing: normal;
            text-decoration: none;
        }

        .info-link:hover, .imdb-link:hover {
            color: #60a5fa;
            text-decoration: underline;
        }

        .cinema-popup {
            display: none;
            position: fixed;
            top: 50%;
            left: 50%;
            transform: translate(-50%, -50%);
            background: #1a1a1a;
            border: 1px solid #333;
            border-radius: 12px;
            padding: 1.5rem;
            z-index: 1000;
            max-width: 320px;
            width: 90%;
            box-shadow: 0 20px 40px rgba(0,0,0,0.5);
        }

        .cinema-popup.active {
            display: block;
        }

        .popup-overlay {
            display: none;
            position: fixed;
            top: 0;
            left: 0;
            right: 0;
            bottom: 0;
            background: rgba(0,0,0,0.7);
            z-index: 999;
        }

        .popup-overlay.active {
            display: block;
        }

        .popup-title {
            font-size: 1.1rem;
            font-weight: 600;
            color: #fff;
            margin-bottom: 0.25rem;
        }

        .popup-area {
            font-size: 0.85rem;
            color: #888;
            margin-bottom: 1rem;
        }

        .popup-address {
            font-size: 0.9rem;
            color: #ccc;
            margin-bottom: 1rem;
        }

        .popup-link {
            display: inline-block;
            padding: 0.5rem 1rem;
            background: #2563eb;
            color: #fff;
            text-decoration: none;
            border-radius: 6px;
            font-size: 0.85rem;
        }

        .popup-link:hover {
            background: #1d4ed8;
        }

        .popup-close {
            position: absolute;
            top: 0.75rem;
            right: 0.75rem;
            background: none;
            border: none;
            color: #666;
            font-size: 1.25rem;
            cursor: pointer;
            padding: 0.25rem;
        }

        .popup-close:hover {
            color: #fff;
        }

        .popup-details {
            font-size: 0.85rem;
            color: #aaa;
            margin-bottom: 0.75rem;
            line-height: 1.6;
        }

        .popup-notes {
            font-size: 0.8rem;
            color: #888;
            font-style: italic;
            margin-bottom: 1rem;
        }

        .popup-links {
            display: flex;
            gap: 0.5rem;
        }

        .popup-link-secondary {
            background: #333;
        }

        .popup-link-secondary:hover {
            background: #444;
        }

        .film-popup {
            display: none;
            position: fixed;
            top: 50%;
            left: 50%;
            transform: translate(-50%, -50%);
            background: #1a1a1a;
            border: 1px solid #333;
            border-radius: 12px;
            padding: 1.5rem;
            z-index: 1000;
            max-width: 500px;
            width: 90%;
            max-height: 80vh;
            overflow-y: auto;
            box-shadow: 0 20px 40px rgba(0,0,0,0.5);
        }

        .film-popup.active {
            display: block;
        }

        .film-poster {
            width: 120px;
            border-radius: 8px;
            float: left;
            margin-right: 1rem;
            margin-bottom: 0.5rem;
        }

        .film-popup-title {
            font-size: 1.2rem;
            font-weight: 600;
            color: #fff;
            margin-bottom: 0.25rem;
        }

        .film-popup-meta {
            font-size: 0.85rem;
            color: #888;
            margin-bottom: 0.75rem;
        }

        .film-popup-overview {
            font-size: 0.9rem;
            color: #ccc;
            line-height: 1.5;
            margin-bottom: 1rem;
            clear: both;
        }

        .film-popup-rating {
            display: inline-block;
            background: #2563eb;
            color: #fff;
            padding: 0.2rem 0.5rem;
            border-radius: 4px;
            font-size: 0.8rem;
            font-weight: 600;
            margin-right: 0.5rem;
        }

        .film-genres {
            margin: 0.5rem 0;
        }

        .genre-tag {
            display: inline-block;
            padding: 0.2rem 0.5rem;
            background: #2a2a2a;
            border-radius: 4px;
            font-size: 0.75rem;
            color: #aaa;
            margin-right: 0.35rem;
            margin-bottom: 0.25rem;
        }

        .film-cast {
            font-size: 0.85rem;
            color: #999;
            margin-bottom: 0.75rem;
        }

        .film-popup-buttons {
            display: flex;
            gap: 0.5rem;
            flex-wrap: wrap;
            margin-top: 1rem;
        }

        .trailer-btn, .imdb-btn, .watch-btn {
            display: inline-block;
            padding: 0.5rem 0.85rem;
            color: #fff;
            text-decoration: none;
            border-radius: 6px;
            font-size: 0.8rem;
            font-weight: 500;
        }

        .trailer-btn {
            background: #dc2626;
        }
        .trailer-btn:hover { background: #b91c1c; }

        .imdb-btn {
            background: #f5c518;
            color: #000;
        }
        .imdb-btn:hover { background: #e4b50f; }

        .watch-btn {
            background: #059669;
        }
        .watch-btn:hover { background: #047857; }

        .film-watch-providers {
            font-size: 0.8rem;
            color: #888;
            margin-top: 0.75rem;
        }

        .screening-card {
            display: flex;
            gap: 1rem;
            padding: 1rem;
            background: #141414;
            border: 1px solid #252525;
            border-radius: 8px;
            margin-bottom: 0.5rem;
            transition: all 0.15s;
        }

        .screening-card:hover {
            background: #1a1a1a;
            border-color: #333;
        }

        .screening-info {
            flex: 1;
        }

        .film-title {
            font-weight: 500;
            color: #fff;
            margin-bottom: 0.5rem;
        }

        .screening-times {
            display: flex;
            flex-wrap: wrap;
            gap: 0.5rem;
        }

        .time-link {
            display: inline-block;
            padding: 0.35rem 0.6rem;
            background: #1e3a5f;
            color: #fff;
            text-decoration: none;
            border-radius: 4px;
            font-size: 0.85rem;
            font-weight: 500;
            transition: background 0.15s;
        }

        .time-link:hover {
            background: #2563eb;
        }

        .tag {
            display: inline-block;
            padding: 0.15rem 0.4rem;
            background: #2a2a2a;
            border-radius: 4px;
            font-size: 0.7rem;
            color: #aaa;
            margin-left: 0.5rem;
        }

        .tag.format-35mm { background: #3d2800; color: #f5a623; }
        .tag.format-4k { background: #1a3d1a; color: #4ade80; }
        .tag.format-70mm { background: #3d1a2e; color: #f472b6; }

        .loading {
            text-align: center;
            padding: 3rem;
            color: #666;
        }

        .empty-state {
            text-align: center;
            padding: 3rem;
            color: #666;
        }

        footer {
            margin-top: 3rem;
            padding-top: 1.5rem;
            border-top: 1px solid #222;
            text-align: center;
            font-size: 0.8rem;
            color: #555;
        }

        footer a {
            color: #888;
        }

        @media (max-width: 600px) {
            .filters { flex-direction: column; }
            .stats { flex-direction: column; gap: 1rem; }
            .screening-card { flex-direction: column; gap: 0.5rem; }
        }
    </style>
</head>
<body>
    <div class="container">
        <header>
            <h1>London Cinema Listings</h1>
            <p class="subtitle">Independent & repertory cinema screenings</p>
        </header>

        <div class="date-nav" id="date-nav"></div>

        <div class="filters" id="cinema-filters"></div>

        <div id="screenings">
            <div class="loading">Loading screenings...</div>
        </div>

        <div class="popup-overlay" id="popup-overlay" onclick="closePopup()"></div>
        <div class="cinema-popup" id="cinema-popup">
            <button class="popup-close" onclick="closePopup()">&times;</button>
            <div class="popup-title" id="popup-title"></div>
            <div class="popup-area" id="popup-area"></div>
            <div class="popup-details" id="popup-details"></div>
            <div class="popup-address" id="popup-address"></div>
            <div class="popup-notes" id="popup-notes"></div>
            <div class="popup-links">
                <a class="popup-link" id="popup-link" href="#" target="_blank">Website</a>
                <a class="popup-link popup-link-secondary" id="popup-map" href="#" target="_blank">Map</a>
            </div>
        </div>

        <div class="popup-overlay" id="film-popup-overlay" onclick="closeFilmPopup()"></div>
        <div class="film-popup" id="film-popup">
            <button class="popup-close" onclick="closeFilmPopup()">&times;</button>
            <div class="film-popup-content" id="film-popup-content">
                <div class="loading">Loading film info...</div>
            </div>
        </div>

        <footer>
            <p>Data from <a href="https://riocinema.org.uk">Rio</a>, <a href="https://www.curzon.com/venues/hoxton/">Curzon Hoxton</a>, <a href="https://princecharlescinema.com/">Prince Charles</a>, <a href="https://www.barbican.org.uk/whats-on/cinema">Barbican</a>, <a href="https://thegardencinema.co.uk">Garden Cinema</a></p>
            <p style="margin-top: 0.5rem;"><a href="/api/screenings">API</a> · <a href="https://github.com/b1rdmania/london-cinema-listings">GitHub</a></p>
        </footer>
    </div>

    <script>
        let allScreenings = [];
        let allCinemas = {};
        let currentCinema = 'all';
        let currentDate = null;

        const TMDB_API_KEY = '5b70f4321b83ac657f3dead793bc93ec';

        function showInfo(cinemaId) {
            const cinema = allCinemas[cinemaId];
            if (!cinema) return;

            document.getElementById('popup-title').textContent = cinema.name;
            document.getElementById('popup-area').textContent = cinema.area;
            document.getElementById('popup-address').textContent = cinema.address;
            document.getElementById('popup-link').href = cinema.website;

            // Build details
            let details = [];
            if (cinema.screens) details.push(`${cinema.screens} screen${cinema.screens > 1 ? 's' : ''}`);
            if (cinema.seats) details.push(`${cinema.seats} seats`);
            if (cinema.sound) details.push(cinema.sound);
            if (cinema.bar) details.push('Licensed bar');
            if (cinema.food) details.push(cinema.food);
            document.getElementById('popup-details').innerHTML = details.join(' · ');

            document.getElementById('popup-notes').textContent = cinema.notes || '';

            // Google Maps link
            const mapUrl = `https://www.google.com/maps/search/?api=1&query=${cinema.lat},${cinema.lon}`;
            document.getElementById('popup-map').href = mapUrl;

            document.getElementById('popup-overlay').classList.add('active');
            document.getElementById('cinema-popup').classList.add('active');
        }

        function closePopup() {
            document.getElementById('popup-overlay').classList.remove('active');
            document.getElementById('cinema-popup').classList.remove('active');
        }

        function cleanFilmTitle(title) {
            // Remove "Members' Screening:" and similar prefixes first
            title = title.replace(/^(Members'? Screening|Preview|Parent & Baby|Relaxed Screening|SCS|Seniors'? Screen|Docs?):\s*/i, '');
            // Remove subtitle/dubbed indicators (with or without brackets)
            title = title.replace(/\s*[\[(]?(subtitled|dubbed|subbed|sub|dub)[\])]?/gi, '');
            // Remove certificate ratings anywhere (with or without parens/brackets)
            title = title.replace(/\s*[\[(]?(U|PG|12A|12|15|18|TBC|NC-17|R|G|NR|PG-13)[\])]?/gi, '');
            // Remove format tags
            title = title.replace(/\s*[\[(]?(35mm|70mm|16mm|4K|IMAX|3D|Dolby|Atmos)[\])]?/gi, '');
            // Remove common suffixes
            title = title.replace(/\s*[-–:+]\s*(Preview|Q&A|Intro|Discussion|Special|Director'?s? Cut|Extended|Remaster(ed)?|Anniversary|Restoration|Screening|recorded|live).*$/i, '');
            // Remove year in parentheses
            title = title.replace(/\s*\(\d{4}\)\s*/g, '');
            // Remove trailing punctuation and whitespace
            title = title.replace(/[\s\-–:,]+$/, '');
            return title.trim();
        }

        async function showFilmInfo(filmTitle) {
            const originalTitle = filmTitle;
            filmTitle = cleanFilmTitle(filmTitle);

            document.getElementById('film-popup-overlay').classList.add('active');
            document.getElementById('film-popup').classList.add('active');
            document.getElementById('film-popup-content').innerHTML = '<div class="loading">Loading film info...</div>';

            try {
                // Search TMDB for the film
                const searchRes = await fetch(
                    `https://api.themoviedb.org/3/search/movie?api_key=${TMDB_API_KEY}&query=${encodeURIComponent(filmTitle)}&include_adult=false&language=en-GB&page=1`
                );
                const searchData = await searchRes.json();

                if (!searchData.results || searchData.results.length === 0) {
                    document.getElementById('film-popup-content').innerHTML = `
                        <div class="film-popup-title">${originalTitle}</div>
                        <p style="color:#888;">Film not found on TMDB</p>
                        <p style="color:#666;font-size:0.8rem;">Searched: "${filmTitle}"</p>
                        <a href="https://www.imdb.com/find/?q=${encodeURIComponent(filmTitle)}" target="_blank" class="popup-link" style="margin-top:1rem;">Search IMDB</a>
                    `;
                    return;
                }

                const movie = searchData.results[0];

                // Get movie details with videos, credits, and watch providers
                const detailsRes = await fetch(
                    `https://api.themoviedb.org/3/movie/${movie.id}?api_key=${TMDB_API_KEY}&append_to_response=videos,credits,watch/providers&language=en-GB`
                );
                const details = await detailsRes.json();

                // Find trailer (prefer Trailer, then Teaser, then any YouTube video)
                let trailerUrl = null;
                if (details.videos && details.videos.results) {
                    const trailer = details.videos.results.find(v => v.type === 'Trailer' && v.site === 'YouTube') ||
                                   details.videos.results.find(v => v.type === 'Teaser' && v.site === 'YouTube') ||
                                   details.videos.results.find(v => v.site === 'YouTube');
                    if (trailer) {
                        trailerUrl = `https://www.youtube.com/watch?v=${trailer.key}`;
                    }
                }

                const posterUrl = movie.poster_path
                    ? `https://image.tmdb.org/t/p/w200${movie.poster_path}`
                    : null;

                const year = movie.release_date ? movie.release_date.substring(0, 4) : '';
                const runtime = details.runtime ? `${details.runtime} min` : '';
                const rating = movie.vote_average ? movie.vote_average.toFixed(1) : null;

                // Get genres
                const genres = details.genres ? details.genres.map(g => g.name).slice(0, 3) : [];

                // Get cast (top 4)
                const cast = details.credits?.cast?.slice(0, 4).map(c => c.name) || [];

                // Get UK watch providers
                const ukProviders = details['watch/providers']?.results?.GB;
                let watchOptions = [];
                if (ukProviders) {
                    if (ukProviders.flatrate) watchOptions.push(...ukProviders.flatrate.slice(0, 2).map(p => p.provider_name));
                    if (ukProviders.rent) watchOptions.push(...ukProviders.rent.slice(0, 2).map(p => `${p.provider_name} (rent)`));
                }

                let html = '';
                if (posterUrl) {
                    html += `<img src="${posterUrl}" class="film-poster" alt="${movie.title}">`;
                }
                html += `<div class="film-popup-title">${movie.title}</div>`;
                html += `<div class="film-popup-meta">${[year, runtime].filter(Boolean).join(' · ')}</div>`;

                if (genres.length) {
                    html += `<div class="film-genres">${genres.map(g => `<span class="genre-tag">${g}</span>`).join('')}</div>`;
                }

                if (rating) {
                    html += `<span class="film-popup-rating">★ ${rating}</span>`;
                }

                if (cast.length) {
                    html += `<div class="film-cast">With: ${cast.join(', ')}</div>`;
                }

                if (movie.overview) {
                    html += `<p class="film-popup-overview">${movie.overview}</p>`;
                }

                // Buttons row
                html += '<div class="film-popup-buttons">';
                if (trailerUrl) {
                    html += `<a href="${trailerUrl}" target="_blank" class="trailer-btn">▶ Trailer</a>`;
                }
                if (details.imdb_id) {
                    html += `<a href="https://www.imdb.com/title/${details.imdb_id}" target="_blank" class="imdb-btn">IMDB</a>`;
                }
                if (ukProviders?.link) {
                    html += `<a href="${ukProviders.link}" target="_blank" class="watch-btn">Where to Watch</a>`;
                }
                html += '</div>';

                if (watchOptions.length) {
                    html += `<div class="film-watch-providers">Available on: ${watchOptions.join(', ')}</div>`;
                }

                document.getElementById('film-popup-content').innerHTML = html;

            } catch (err) {
                document.getElementById('film-popup-content').innerHTML = `
                    <div class="film-popup-title">${filmTitle}</div>
                    <p style="color:#888;">Could not load film info</p>
                `;
            }
        }

        function closeFilmPopup() {
            document.getElementById('film-popup-overlay').classList.remove('active');
            document.getElementById('film-popup').classList.remove('active');
        }

        async function loadData() {
            try {
                const [screeningsRes, cinemasRes] = await Promise.all([
                    fetch('/api/screenings'),
                    fetch('/api/cinemas')
                ]);

                const screeningsData = await screeningsRes.json();
                const cinemasData = await cinemasRes.json();

                allScreenings = screeningsData.screenings || [];

                // Store cinema info for popups
                cinemasData.cinemas.forEach(c => {
                    allCinemas[c.id] = c;
                });

                // Build cinema filters
                const filtersEl = document.getElementById('cinema-filters');
                cinemasData.cinemas.forEach(cinema => {
                    const btn = document.createElement('button');
                    btn.className = 'filter-btn';
                    btn.dataset.cinema = cinema.id;
                    btn.textContent = cinema.name;
                    btn.onclick = () => filterByCinema(cinema.id);
                    filtersEl.appendChild(btn);
                });

                // Build date nav
                buildDateNav();

                // Set default to today
                const today = new Date().toISOString().split('T')[0];
                currentDate = today;

                renderScreenings();
            } catch (err) {
                document.getElementById('screenings').innerHTML =
                    '<div class="empty-state">Error loading screenings. Please try again.</div>';
            }
        }

        function buildDateNav() {
            const dateNav = document.getElementById('date-nav');
            const dates = [...new Set(allScreenings.map(s => s.start_time.split('T')[0]))].sort();

            const today = new Date().toISOString().split('T')[0];
            const tomorrow = new Date(Date.now() + 86400000).toISOString().split('T')[0];

            // Create TODAY button
            const todayBtn = document.createElement('button');
            todayBtn.className = 'date-btn';
            todayBtn.dataset.date = today;
            todayBtn.innerHTML = '<strong>TODAY</strong>';
            todayBtn.onclick = () => filterByDate(today);
            dateNav.appendChild(todayBtn);

            // Create TOMORROW button
            const tomorrowBtn = document.createElement('button');
            tomorrowBtn.className = 'date-btn';
            tomorrowBtn.dataset.date = tomorrow;
            tomorrowBtn.innerHTML = '<strong>TOMORROW</strong>';
            tomorrowBtn.onclick = () => filterByDate(tomorrow);
            dateNav.appendChild(tomorrowBtn);
        }

        function filterByCinema(cinemaId) {
            currentCinema = cinemaId;
            document.querySelectorAll('.filter-btn').forEach(btn => {
                btn.classList.toggle('active', btn.dataset.cinema === cinemaId);
            });
            renderScreenings();
        }

        function filterByDate(date) {
            currentDate = date;
            document.querySelectorAll('.date-btn').forEach(btn => {
                btn.classList.toggle('active', btn.dataset.date === date);
            });
            renderScreenings();
        }

        function renderScreenings() {
            let filtered = allScreenings;

            if (currentCinema !== 'all') {
                filtered = filtered.filter(s => s.cinema_id === currentCinema);
            }

            if (currentDate) {
                filtered = filtered.filter(s => s.start_time.startsWith(currentDate));
            }

            // Highlight active date
            document.querySelectorAll('.date-btn').forEach(btn => {
                btn.classList.toggle('active', btn.dataset.date === currentDate);
            });

            const container = document.getElementById('screenings');

            if (filtered.length === 0) {
                container.innerHTML = '<div class="empty-state">No screenings found for this selection.</div>';
                return;
            }

            // Group by cinema, then by film
            const byCinema = {};
            filtered.forEach(s => {
                if (!byCinema[s.cinema_name]) byCinema[s.cinema_name] = {};
                if (!byCinema[s.cinema_name][s.film_title]) byCinema[s.cinema_name][s.film_title] = [];
                byCinema[s.cinema_name][s.film_title].push(s);
            });

            let html = '';
            Object.entries(byCinema).sort().forEach(([cinema, films]) => {
                // Find cinema ID from first screening
                const firstFilm = Object.values(films)[0];
                const cinemaId = firstFilm[0]?.cinema_id || '';

                html += `<div class="screening-group">`;
                html += `<div class="group-header">${cinema} <span class="info-link" onclick="showInfo('${cinemaId}')">(info)</span></div>`;

                // Sort films by earliest showtime
                const sortedFilms = Object.entries(films).sort((a, b) => {
                    const aTime = Math.min(...a[1].map(s => new Date(s.start_time).getTime()));
                    const bTime = Math.min(...b[1].map(s => new Date(s.start_time).getTime()));
                    return aTime - bTime;
                });

                sortedFilms.forEach(([filmTitle, screenings]) => {
                    // Sort screenings by time
                    screenings.sort((a, b) => a.start_time.localeCompare(b.start_time));

                    // Build times list
                    const times = screenings.map(s => {
                        const time = new Date(s.start_time).toLocaleTimeString('en-GB', {
                            hour: '2-digit',
                            minute: '2-digit'
                        });
                        return `<a href="${s.booking_url}" target="_blank" class="time-link">${time}</a>`;
                    }).join(' ');

                    // Get tags from first screening
                    let tags = '';
                    const firstNote = screenings[0].notes;
                    if (firstNote) {
                        if (firstNote.includes('35mm')) tags += '<span class="tag format-35mm">35mm</span>';
                        else if (firstNote.includes('4K')) tags += '<span class="tag format-4k">4K</span>';
                        else if (firstNote.includes('70mm')) tags += '<span class="tag format-70mm">70mm</span>';
                    }

                    html += `
                        <div class="screening-card">
                            <div class="screening-info">
                                <div class="film-title">${filmTitle}${tags} <span class="info-link" onclick="showFilmInfo('${filmTitle.replace(/'/g, "\\'")}')">(info)</span></div>
                                <div class="screening-times">${times}</div>
                            </div>
                        </div>
                    `;
                });

                html += '</div>';
            });

            container.innerHTML = html;
        }

        loadData();
    </script>
</body>
</html>
"""
