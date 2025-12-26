"""
FastAPI web API for London Cinema Listings.
Deployed to Vercel serverless functions.
"""

from datetime import datetime, timedelta
from typing import Optional
import json
import os
import sys

from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

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
        "id": "rio-cinema",
        "name": "Rio Cinema",
        "address": "107 Kingsland High St, London E8 2PB",
        "lat": 51.5485,
        "lon": -0.0754,
        "website": "https://riocinema.org.uk"
    },
    "curzon-hoxton": {
        "id": "curzon-hoxton",
        "name": "Curzon Hoxton",
        "address": "58-60 Hoxton Square, London N1 6PB",
        "lat": 51.5285,
        "lon": -0.0815,
        "website": "https://www.curzon.com/venues/hoxton/"
    },
    "prince-charles": {
        "id": "prince-charles-cinema",
        "name": "Prince Charles Cinema",
        "address": "7 Leicester Place, London WC2H 7BY",
        "lat": 51.5112,
        "lon": -0.1304,
        "website": "https://princecharlescinema.com/"
    },
    "barbican": {
        "id": "barbican-cinema",
        "name": "Barbican Cinema",
        "address": "Silk Street, London EC2Y 8DS",
        "lat": 51.5200,
        "lon": -0.0936,
        "website": "https://www.barbican.org.uk/whats-on/cinema"
    }
}


@app.get("/")
async def root():
    """API root - returns basic info and links."""
    return {
        "name": "London Cinema Listings API",
        "version": "0.1.0",
        "endpoints": {
            "cinemas": "/cinemas",
            "screenings": "/screenings",
            "today": "/screenings/today",
            "docs": "/docs"
        },
        "cinemas_available": list(CINEMAS.keys())
    }


@app.get("/cinemas")
async def list_cinemas():
    """List all available cinemas."""
    return {"cinemas": list(CINEMAS.values())}


@app.get("/cinemas/{cinema_id}")
async def get_cinema(cinema_id: str):
    """Get details for a specific cinema."""
    if cinema_id not in CINEMAS:
        return {"error": f"Cinema '{cinema_id}' not found"}
    return CINEMAS[cinema_id]


@app.get("/screenings")
async def get_screenings(
    cinema: Optional[str] = Query(None, description="Filter by cinema ID"),
    date: Optional[str] = Query(None, description="Filter by date (YYYY-MM-DD)"),
    days: int = Query(7, description="Number of days ahead to fetch")
):
    """
    Get upcoming screenings.

    Note: In production, this would fetch live data from scrapers.
    For the demo, returns sample data structure.
    """
    # In production, we'd run the scrapers here
    # For now, return the API structure
    return {
        "screenings": [],
        "message": "Live scraping not enabled in serverless mode. Use CLI for live data.",
        "filters": {
            "cinema": cinema,
            "date": date,
            "days": days
        },
        "available_cinemas": list(CINEMAS.keys())
    }


@app.get("/screenings/today")
async def get_today_screenings(cinema: Optional[str] = None):
    """Get today's screenings."""
    today = datetime.now().strftime("%Y-%m-%d")
    return await get_screenings(cinema=cinema, date=today, days=1)


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy", "timestamp": datetime.now().isoformat()}


# Simple HTML frontend
@app.get("/app", response_class=HTMLResponse)
async def web_app():
    """Simple HTML frontend."""
    html = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>London Cinema Listings</title>
    <style>
        * { box-sizing: border-box; margin: 0; padding: 0; }
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: #0a0a0a;
            color: #e0e0e0;
            min-height: 100vh;
            padding: 2rem;
        }
        .container { max-width: 800px; margin: 0 auto; }
        h1 {
            font-size: 2rem;
            margin-bottom: 0.5rem;
            color: #fff;
        }
        .subtitle {
            color: #888;
            margin-bottom: 2rem;
        }
        .cinema-card {
            background: #1a1a1a;
            border: 1px solid #333;
            border-radius: 8px;
            padding: 1.5rem;
            margin-bottom: 1rem;
        }
        .cinema-card h2 {
            color: #fff;
            font-size: 1.25rem;
            margin-bottom: 0.5rem;
        }
        .cinema-card .address {
            color: #888;
            font-size: 0.875rem;
            margin-bottom: 1rem;
        }
        .cinema-card a {
            color: #4da6ff;
            text-decoration: none;
        }
        .cinema-card a:hover { text-decoration: underline; }
        .info-box {
            background: #1a2a1a;
            border: 1px solid #2a4a2a;
            border-radius: 8px;
            padding: 1.5rem;
            margin-top: 2rem;
        }
        .info-box h3 { color: #6c6; margin-bottom: 0.5rem; }
        code {
            background: #2a2a2a;
            padding: 0.25rem 0.5rem;
            border-radius: 4px;
            font-size: 0.875rem;
        }
        .api-link {
            display: inline-block;
            margin-top: 1rem;
            padding: 0.5rem 1rem;
            background: #333;
            color: #fff;
            text-decoration: none;
            border-radius: 4px;
        }
        .api-link:hover { background: #444; }
    </style>
</head>
<body>
    <div class="container">
        <h1>London Cinema Listings</h1>
        <p class="subtitle">Independent cinema screenings across London</p>

        <div id="cinemas"></div>

        <div class="info-box">
            <h3>CLI Usage</h3>
            <p>For live screening data, run the CLI locally:</p>
            <p style="margin-top: 0.5rem;">
                <code>python main.py</code>
            </p>
            <a href="/docs" class="api-link">API Documentation</a>
        </div>
    </div>

    <script>
        fetch('/cinemas')
            .then(r => r.json())
            .then(data => {
                const container = document.getElementById('cinemas');
                data.cinemas.forEach(cinema => {
                    container.innerHTML += `
                        <div class="cinema-card">
                            <h2>${cinema.name}</h2>
                            <p class="address">${cinema.address}</p>
                            <a href="${cinema.website}" target="_blank">Visit website &rarr;</a>
                        </div>
                    `;
                });
            });
    </script>
</body>
</html>
    """
    return html
