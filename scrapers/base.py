"""Base scraper class and data models for cinema listings."""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional
import hashlib


@dataclass
class Screening:
    """A single film screening at a cinema."""
    cinema_id: str
    cinema_name: str
    film_title: str
    start_time: datetime
    booking_url: str
    format: Optional[str] = None
    screen: Optional[str] = None
    end_time: Optional[datetime] = None
    notes: Optional[str] = None
    scraped_at: datetime = field(default_factory=datetime.now)

    @property
    def id(self) -> str:
        """Generate unique ID from cinema + film + datetime."""
        key = f"{self.cinema_id}:{self.film_title}:{self.start_time.isoformat()}"
        return hashlib.md5(key.encode()).hexdigest()[:16]


@dataclass
class Film:
    """Basic film information."""
    title: str
    year: Optional[int] = None
    director: Optional[str] = None
    runtime_mins: Optional[int] = None
    certificate: Optional[str] = None
    synopsis: Optional[str] = None


@dataclass
class Cinema:
    """Cinema venue information."""
    id: str
    name: str
    address: str
    postcode: str
    website: str
    chain: Optional[str] = None
    lat: Optional[float] = None
    lon: Optional[float] = None


class BaseScraper(ABC):
    """Abstract base class for cinema scrapers."""

    def __init__(self, cinema: Cinema):
        self.cinema = cinema

    @abstractmethod
    async def scrape(self, days_ahead: int = 7) -> list[Screening]:
        """
        Scrape screenings from the cinema website.

        Args:
            days_ahead: Number of days to look ahead for screenings.

        Returns:
            List of Screening objects.
        """
        pass

    @abstractmethod
    async def get_films(self) -> list[Film]:
        """
        Get list of films currently showing.

        Returns:
            List of Film objects with basic information.
        """
        pass
