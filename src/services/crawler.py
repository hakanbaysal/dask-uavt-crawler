"""
Hierarchical crawler for DASK UAVT address codes.

Traverses: City → District → Village → Quarter → Street → Building → Section
Uses checkpoint-based progress tracking for crash recovery.
"""

from __future__ import annotations

import json
import logging
from typing import List

from src.client.dask_client import DaskClient, ApiError
from src.client.html_parser import HtmlParser, ParseError
from src.config import Config
from src.models.address import (
    Building,
    City,
    District,
    Quarter,
    Section,
    Street,
    Village,
)
from src.repository.db import Database, DatabaseError
from src.services.progress import Checkpoint, ProgressTracker


class CrawlerError(Exception):
    """Raised when the crawler encounters an unrecoverable error."""


class Crawler:
    """
    Main crawler service.

    Walks the DASK UAVT hierarchy top-down, storing results in PostgreSQL
    and saving checkpoints after each node is fully processed.
    """

    def __init__(
        self,
        config: Config,
        client: DaskClient,
        db: Database,
        parser: HtmlParser,
        progress: ProgressTracker,
    ) -> None:
        self._config = config
        self._client = client
        self._db = db
        self._parser = parser
        self._progress = progress
        self._logger = logging.getLogger("dask_uavt.crawler")
        self._checkpoint: Checkpoint = Checkpoint()

    # ── JSON Response Parsing ─────────────────────────────────────────

    def _parse_json_list(self, raw: str) -> list[dict]:
        """
        Parse JSON array from API response.

        The API wraps results in {"yt": [...]}.
        """
        try:
            data = json.loads(raw)
            if isinstance(data, dict) and "yt" in data:
                return data["yt"]
            if isinstance(data, list):
                return data
            return []
        except (json.JSONDecodeError, TypeError) as exc:
            self._logger.warning("Failed to parse JSON: %s", exc)
            return []

    # ── Level Fetchers ────────────────────────────────────────────────

    def _fetch_cities(self) -> List[City]:
        """Fetch all cities (il, u=0)."""
        raw = self._client.load("il", 0)
        items = self._parse_json_list(raw)
        return [City(code=int(item["i"]), name=item["t"]) for item in items if "i" in item]

    def _fetch_districts(self, city_code: int) -> List[District]:
        """Fetch districts for a city (ce, u=city_code)."""
        raw = self._client.load("ce", city_code)
        items = self._parse_json_list(raw)
        return [
            District(code=int(item["i"]), name=item["t"], city_code=city_code)
            for item in items if "i" in item
        ]

    def _fetch_villages(self, district_code: int) -> List[Village]:
        """Fetch villages for a district (vl, u=district_code)."""
        raw = self._client.load("vl", district_code)
        items = self._parse_json_list(raw)
        return [
            Village(code=int(item["i"]), name=item["t"], district_code=district_code)
            for item in items if "i" in item
        ]

    def _fetch_quarters(self, village_code: int) -> List[Quarter]:
        """Fetch quarters for a village (mh, u=village_code)."""
        raw = self._client.load("mh", village_code)
        items = self._parse_json_list(raw)
        return [
            Quarter(code=int(item["i"]), name=item["t"], village_code=village_code)
            for item in items if "i" in item
        ]

    def _fetch_streets(self, quarter_code: int) -> List[Street]:
        """Fetch streets for a quarter (sf, u=quarter_code) — HTML response."""
        raw = self._client.load("sf", quarter_code)
        return self._parser.parse_streets(raw, quarter_code)

    def _fetch_buildings(self, street_code: int) -> List[Building]:
        """Fetch buildings for a street (dk, u=street_code) — HTML response."""
        raw = self._client.load("dk", street_code)
        return self._parser.parse_buildings(raw, street_code)

    def _fetch_sections(self, building_code: int) -> List[Section]:
        """Fetch sections for a building (ick, u=building_code) — HTML response."""
        raw = self._client.load("ick", building_code)
        return self._parser.parse_sections(raw, building_code)

    # ── Hierarchy Traversal ───────────────────────────────────────────

    def _should_skip(self, code: int, checkpoint_code: int) -> bool:
        """Return True if this node was already processed (before checkpoint)."""
        return checkpoint_code > 0 and code <= checkpoint_code

    def _crawl_buildings(self, street: Street) -> None:
        """Crawl all buildings and their sections for a street."""
        try:
            buildings = self._fetch_buildings(street.code)
            if buildings:
                self._db.insert_buildings(buildings)
        except (ApiError, DatabaseError) as exc:
            self._logger.error("Error crawling buildings for %s: %s", street, exc)
            return

        for building in buildings:
            if self._should_skip(building.code, self._checkpoint.building_code):
                self._logger.debug("Skipping building %s (checkpoint)", building)
                continue

            try:
                sections = self._fetch_sections(building.code)
                if sections:
                    self._db.insert_sections(sections)
                    self._logger.info(
                        "  └─ Building %s: %d sections", building.building_no, len(sections)
                    )
            except (ApiError, DatabaseError, ParseError) as exc:
                self._logger.error("Error crawling sections for %s: %s", building, exc)

            # Save progress after each building
            self._checkpoint.building_code = building.code
            self._progress.save(self._checkpoint)

        # Reset building checkpoint when street is done
        self._checkpoint.building_code = 0

    def _crawl_streets(self, quarter: Quarter) -> None:
        """Crawl all streets and their children for a quarter."""
        try:
            streets = self._fetch_streets(quarter.code)
            if streets:
                self._db.insert_streets(streets)
        except (ApiError, DatabaseError) as exc:
            self._logger.error("Error crawling streets for %s: %s", quarter, exc)
            return

        for street in streets:
            if self._should_skip(street.code, self._checkpoint.street_code):
                self._logger.debug("Skipping street %s (checkpoint)", street)
                continue

            self._logger.info("  ├─ Street: %s", street)
            self._crawl_buildings(street)

            self._checkpoint.street_code = street.code
            self._checkpoint.reset_below_street()
            self._progress.save(self._checkpoint)

        self._checkpoint.street_code = 0

    def _crawl_quarters(self, village: Village) -> None:
        """Crawl all quarters and their children for a village."""
        try:
            quarters = self._fetch_quarters(village.code)
            if quarters:
                self._db.insert_quarters(quarters)
        except (ApiError, DatabaseError) as exc:
            self._logger.error("Error crawling quarters for %s: %s", village, exc)
            return

        for quarter in quarters:
            if self._should_skip(quarter.code, self._checkpoint.quarter_code):
                self._logger.debug("Skipping quarter %s (checkpoint)", quarter)
                continue

            self._logger.info("  Quarter: %s", quarter)
            self._crawl_streets(quarter)

            self._checkpoint.quarter_code = quarter.code
            self._checkpoint.reset_below_quarter()
            self._progress.save(self._checkpoint)

        self._checkpoint.quarter_code = 0

    def _crawl_villages(self, district: District) -> None:
        """Crawl all villages and their children for a district."""
        try:
            villages = self._fetch_villages(district.code)
            if villages:
                self._db.insert_villages(villages)
        except (ApiError, DatabaseError) as exc:
            self._logger.error("Error crawling villages for %s: %s", district, exc)
            return

        for village in villages:
            if self._should_skip(village.code, self._checkpoint.village_code):
                self._logger.debug("Skipping village %s (checkpoint)", village)
                continue

            self._logger.info(" Village: %s", village)
            self._crawl_quarters(village)

            self._checkpoint.village_code = village.code
            self._checkpoint.reset_below_village()
            self._progress.save(self._checkpoint)

        self._checkpoint.village_code = 0

    def _crawl_districts(self, city: City) -> None:
        """Crawl all districts and their children for a city."""
        try:
            districts = self._fetch_districts(city.code)
            if districts:
                self._db.insert_districts(districts)
        except (ApiError, DatabaseError) as exc:
            self._logger.error("Error crawling districts for %s: %s", city, exc)
            return

        for district in districts:
            if self._should_skip(district.code, self._checkpoint.district_code):
                self._logger.debug("Skipping district %s (checkpoint)", district)
                continue

            self._logger.info("District: %s", district)
            self._crawl_villages(district)

            self._checkpoint.district_code = district.code
            self._checkpoint.reset_below_district()
            self._progress.save(self._checkpoint)

        self._checkpoint.district_code = 0

    # ── Public Entry Point ────────────────────────────────────────────

    def run(self) -> None:
        """
        Start the full hierarchical crawl.

        Resumes from the last checkpoint if one exists.
        Saves progress after each completed node.
        """
        self._logger.info("=" * 60)
        self._logger.info("DASK UAVT Crawler starting...")
        self._logger.info("=" * 60)

        # Load or create checkpoint
        self._checkpoint = self._progress.load()

        if self._checkpoint.completed:
            self._logger.info("Previous crawl already completed. Clear checkpoint to re-run.")
            return

        # Fetch all cities
        try:
            cities = self._fetch_cities()
            self._db.insert_cities(cities)
            self._logger.info("Found %d cities", len(cities))
        except (ApiError, DatabaseError) as exc:
            raise CrawlerError(f"Failed to fetch cities: {exc}") from exc

        # Apply optional city filter
        if self._config.start_city_code > 0:
            cities = [c for c in cities if c.code >= self._config.start_city_code]
        if self._config.end_city_code > 0:
            cities = [c for c in cities if c.code <= self._config.end_city_code]

        for city in cities:
            if self._should_skip(city.code, self._checkpoint.city_code):
                self._logger.debug("Skipping city %s (checkpoint)", city)
                continue

            self._logger.info("=" * 40)
            self._logger.info("City: %s", city)
            self._logger.info("=" * 40)

            self._crawl_districts(city)

            self._checkpoint.city_code = city.code
            self._checkpoint.reset_below_city()
            self._progress.save(self._checkpoint)

        # Mark completed
        self._checkpoint.completed = True
        self._progress.save(self._checkpoint)

        # Print summary
        try:
            counts = self._db.get_total_counts()
            self._logger.info("=" * 60)
            self._logger.info("Crawl completed! Summary:")
            for table, count in counts.items():
                self._logger.info("  %s: %d", table, count)
            self._logger.info("=" * 60)
        except DatabaseError:
            self._logger.info("Crawl completed!")
