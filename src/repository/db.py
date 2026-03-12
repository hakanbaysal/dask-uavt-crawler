"""PostgreSQL database connection and CRUD operations."""

from __future__ import annotations

import logging
from contextlib import contextmanager
from typing import Generator, Optional

import psycopg2
from psycopg2.extras import execute_values

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


class DatabaseError(Exception):
    """Raised when a database operation fails."""


class Database:
    """
    PostgreSQL repository for UAVT address data.

    Uses connection pooling via psycopg2 and provides
    bulk-insert methods for each hierarchy level.
    """

    def __init__(self, config: Config) -> None:
        self._config = config
        self._logger = logging.getLogger("dask_uavt.db")
        self._conn: Optional[psycopg2.extensions.connection] = None

    # ── Connection Management ─────────────────────────────────────────

    def connect(self) -> None:
        """Establish database connection."""
        try:
            self._conn = psycopg2.connect(self._config.db_dsn)
            self._conn.autocommit = False
            self._logger.info("Database connected: %s", self._config.db_name)
        except psycopg2.Error as exc:
            raise DatabaseError(f"Failed to connect to database: {exc}") from exc

    def close(self) -> None:
        """Close database connection."""
        if self._conn and not self._conn.closed:
            self._conn.close()
            self._logger.info("Database connection closed.")

    @contextmanager
    def _cursor(self) -> Generator:
        """Context manager for database cursor with auto-commit."""
        if not self._conn or self._conn.closed:
            self.connect()

        cursor = self._conn.cursor()
        try:
            yield cursor
            self._conn.commit()
        except psycopg2.Error as exc:
            self._conn.rollback()
            self._logger.error("Database error (rolled back): %s", exc)
            raise DatabaseError(str(exc)) from exc
        finally:
            cursor.close()

    def __enter__(self) -> Database:
        self.connect()
        return self

    def __exit__(self, *args) -> None:
        self.close()

    # ── CRUD: Cities ──────────────────────────────────────────────────

    def insert_cities(self, cities: list[City]) -> int:
        """Bulk-insert cities. Returns number of rows inserted."""
        if not cities:
            return 0

        sql = """
            INSERT INTO cities (code, name)
            VALUES %s
            ON CONFLICT (code) DO UPDATE SET name = EXCLUDED.name
        """
        values = [(c.code, c.name) for c in cities]

        with self._cursor() as cur:
            execute_values(cur, sql, values)
            return len(values)

    # ── CRUD: Districts ───────────────────────────────────────────────

    def insert_districts(self, districts: list[District]) -> int:
        """Bulk-insert districts. Returns number of rows inserted."""
        if not districts:
            return 0

        sql = """
            INSERT INTO districts (code, name, city_code)
            VALUES %s
            ON CONFLICT (code) DO UPDATE SET name = EXCLUDED.name
        """
        values = [(d.code, d.name, d.city_code) for d in districts]

        with self._cursor() as cur:
            execute_values(cur, sql, values)
            return len(values)

    # ── CRUD: Villages ────────────────────────────────────────────────

    def insert_villages(self, villages: list[Village]) -> int:
        """Bulk-insert villages. Returns number of rows inserted."""
        if not villages:
            return 0

        sql = """
            INSERT INTO villages (code, name, district_code)
            VALUES %s
            ON CONFLICT (code) DO UPDATE SET name = EXCLUDED.name
        """
        values = [(v.code, v.name, v.district_code) for v in villages]

        with self._cursor() as cur:
            execute_values(cur, sql, values)
            return len(values)

    # ── CRUD: Quarters ────────────────────────────────────────────────

    def insert_quarters(self, quarters: list[Quarter]) -> int:
        """Bulk-insert quarters. Returns number of rows inserted."""
        if not quarters:
            return 0

        sql = """
            INSERT INTO quarters (code, name, village_code)
            VALUES %s
            ON CONFLICT (code) DO UPDATE SET name = EXCLUDED.name
        """
        values = [(q.code, q.name, q.village_code) for q in quarters]

        with self._cursor() as cur:
            execute_values(cur, sql, values)
            return len(values)

    # ── CRUD: Streets ─────────────────────────────────────────────────

    def insert_streets(self, streets: list[Street]) -> int:
        """Bulk-insert streets. Returns number of rows inserted."""
        if not streets:
            return 0

        sql = """
            INSERT INTO streets (code, name, street_type, quarter_code)
            VALUES %s
            ON CONFLICT (code) DO UPDATE SET
                name = EXCLUDED.name,
                street_type = EXCLUDED.street_type
        """
        values = [(s.code, s.name, s.street_type, s.quarter_code) for s in streets]

        with self._cursor() as cur:
            execute_values(cur, sql, values)
            return len(values)

    # ── CRUD: Buildings ───────────────────────────────────────────────

    def insert_buildings(self, buildings: list[Building]) -> int:
        """Bulk-insert buildings. Returns number of rows inserted."""
        if not buildings:
            return 0

        sql = """
            INSERT INTO buildings (code, building_no, building_code, site_name, building_name, street_code)
            VALUES %s
            ON CONFLICT (code) DO UPDATE SET
                building_no = EXCLUDED.building_no,
                building_code = EXCLUDED.building_code,
                site_name = EXCLUDED.site_name,
                building_name = EXCLUDED.building_name
        """
        values = [
            (b.code, b.building_no, b.building_code, b.site_name, b.building_name, b.street_code)
            for b in buildings
        ]

        with self._cursor() as cur:
            execute_values(cur, sql, values)
            return len(values)

    # ── CRUD: Sections ────────────────────────────────────────────────

    def insert_sections(self, sections: list[Section]) -> int:
        """Bulk-insert sections (units). Returns number of rows inserted."""
        if not sections:
            return 0

        sql = """
            INSERT INTO sections (uavt_code, door_no, building_code)
            VALUES %s
            ON CONFLICT (uavt_code) DO UPDATE SET door_no = EXCLUDED.door_no
        """
        values = [(s.uavt_code, s.door_no, s.building_code) for s in sections]

        with self._cursor() as cur:
            execute_values(cur, sql, values)
            return len(values)

    # ── Query Helpers ─────────────────────────────────────────────────

    def get_total_counts(self) -> dict[str, int]:
        """Return row counts for all tables."""
        tables = [
            "cities", "districts", "villages", "quarters",
            "streets", "buildings", "sections",
        ]
        counts = {}
        with self._cursor() as cur:
            for table in tables:
                cur.execute(f"SELECT COUNT(*) FROM {table}")  # noqa: S608
                counts[table] = cur.fetchone()[0]
        return counts
