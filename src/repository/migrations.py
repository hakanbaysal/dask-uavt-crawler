"""Database migration — table creation for DASK UAVT schema."""

from __future__ import annotations

import logging

import psycopg2

from src.config import Config


class MigrationError(Exception):
    """Raised when a migration step fails."""


# DDL statements for the address hierarchy
_TABLES_SQL = """
-- Cities (İller)
CREATE TABLE IF NOT EXISTS cities (
    code        INTEGER PRIMARY KEY,
    name        VARCHAR(100) NOT NULL,
    created_at  TIMESTAMP DEFAULT NOW()
);

-- Districts (İlçeler)
CREATE TABLE IF NOT EXISTS districts (
    code        INTEGER PRIMARY KEY,
    name        VARCHAR(100) NOT NULL,
    city_code   INTEGER NOT NULL REFERENCES cities(code),
    created_at  TIMESTAMP DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_districts_city ON districts(city_code);

-- Villages / Sub-districts (Bucak / Köy)
CREATE TABLE IF NOT EXISTS villages (
    code          INTEGER PRIMARY KEY,
    name          VARCHAR(150) NOT NULL,
    district_code INTEGER NOT NULL REFERENCES districts(code),
    created_at    TIMESTAMP DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_villages_district ON villages(district_code);

-- Quarters (Mahalleler)
CREATE TABLE IF NOT EXISTS quarters (
    code         INTEGER PRIMARY KEY,
    name         VARCHAR(150) NOT NULL,
    village_code INTEGER NOT NULL REFERENCES villages(code),
    created_at   TIMESTAMP DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_quarters_village ON quarters(village_code);

-- Streets (Cadde / Sokak)
CREATE TABLE IF NOT EXISTS streets (
    code         INTEGER PRIMARY KEY,
    name         VARCHAR(200) NOT NULL,
    street_type  VARCHAR(50) DEFAULT '',
    quarter_code INTEGER NOT NULL REFERENCES quarters(code),
    created_at   TIMESTAMP DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_streets_quarter ON streets(quarter_code);

-- Buildings (Binalar)
CREATE TABLE IF NOT EXISTS buildings (
    code          INTEGER PRIMARY KEY,
    building_no   VARCHAR(50) DEFAULT '',
    building_code VARCHAR(50) DEFAULT '',
    site_name     VARCHAR(200) DEFAULT '',
    building_name VARCHAR(200) DEFAULT '',
    street_code   INTEGER NOT NULL REFERENCES streets(code),
    created_at    TIMESTAMP DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_buildings_street ON buildings(street_code);

-- Sections / Units (İç Kapı — Bağımsız Bölüm)
CREATE TABLE IF NOT EXISTS sections (
    uavt_code     INTEGER PRIMARY KEY,
    door_no       VARCHAR(50) DEFAULT '',
    building_code INTEGER NOT NULL REFERENCES buildings(code),
    created_at    TIMESTAMP DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_sections_building ON sections(building_code);
"""


def run_migrations(config: Config) -> None:
    """
    Create all tables if they don't exist.

    Args:
        config: Application configuration with DB credentials.

    Raises:
        MigrationError: If DDL execution fails.
    """
    logger = logging.getLogger("dask_uavt.migrations")

    try:
        conn = psycopg2.connect(config.db_dsn)
        conn.autocommit = True
        cursor = conn.cursor()

        logger.info("Running database migrations...")
        cursor.execute(_TABLES_SQL)
        logger.info("Migrations completed successfully.")

        cursor.close()
        conn.close()

    except psycopg2.Error as exc:
        raise MigrationError(f"Migration failed: {exc}") from exc
