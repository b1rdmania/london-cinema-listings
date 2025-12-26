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
        "website": "https://riocinema.org.uk"
    },
    "curzon-hoxton": {
        "id": "curzon-hoxton",
        "name": "Curzon Hoxton",
        "area": "Hoxton",
        "address": "58-60 Hoxton Square, London N1 6PB",
        "lat": 51.5285,
        "lon": -0.0815,
        "website": "https://www.curzon.com/venues/hoxton/"
    },
    "prince-charles-cinema": {
        "id": "prince-charles-cinema",
        "name": "Prince Charles Cinema",
        "area": "Leicester Square",
        "address": "7 Leicester Place, London WC2H 7BY",
        "lat": 51.5112,
        "lon": -0.1304,
        "website": "https://princecharlescinema.com/"
    },
    "barbican-cinema": {
        "id": "barbican-cinema",
        "name": "Barbican Cinema",
        "area": "Barbican",
        "address": "Silk Street, London EC2Y 8DS",
        "lat": 51.5200,
        "lon": -0.0936,
        "website": "https://www.barbican.org.uk/whats-on/cinema"
    },
    "garden-cinema": {
        "id": "garden-cinema",
        "name": "The Garden Cinema",
        "area": "Covent Garden",
        "address": "39-41 Parker Street, London WC2B 5PQ",
        "lat": 51.5160,
        "lon": -0.1224,
        "website": "https://thegardencinema.co.uk"
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

        .info-link {
            font-size: 0.7rem;
            color: #2563eb;
            cursor: pointer;
            text-transform: none;
            letter-spacing: normal;
        }

        .info-link:hover {
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
            <div class="popup-address" id="popup-address"></div>
            <a class="popup-link" id="popup-link" href="#" target="_blank">Visit Website</a>
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

        function showInfo(cinemaId) {
            const cinema = allCinemas[cinemaId];
            if (!cinema) return;

            document.getElementById('popup-title').textContent = cinema.name;
            document.getElementById('popup-area').textContent = cinema.area;
            document.getElementById('popup-address').textContent = cinema.address;
            document.getElementById('popup-link').href = cinema.website;

            document.getElementById('popup-overlay').classList.add('active');
            document.getElementById('cinema-popup').classList.add('active');
        }

        function closePopup() {
            document.getElementById('popup-overlay').classList.remove('active');
            document.getElementById('cinema-popup').classList.remove('active');
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
                                <div class="film-title">${filmTitle}${tags}</div>
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
