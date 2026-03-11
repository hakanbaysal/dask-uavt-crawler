import psycopg2
from psycopg2.extras import execute_values
from src.config import DB_HOST, DB_PORT, DB_NAME, DB_USER, DB_PASS


def get_connection():
    return psycopg2.connect(
        host=DB_HOST, port=DB_PORT,
        dbname=DB_NAME, user=DB_USER, password=DB_PASS
    )


def init_db():
    """Create tables if they don't exist."""
    conn = get_connection()
    cur = conn.cursor()

    cur.execute("""
        CREATE TABLE IF NOT EXISTS cities (
            code VARCHAR(10) PRIMARY KEY,
            name TEXT NOT NULL,
            crawled_at TIMESTAMP DEFAULT NOW()
        );

        CREATE TABLE IF NOT EXISTS districts (
            code VARCHAR(10) PRIMARY KEY,
            city_code VARCHAR(10) REFERENCES cities(code),
            name TEXT NOT NULL,
            crawled_at TIMESTAMP DEFAULT NOW()
        );

        CREATE TABLE IF NOT EXISTS villages (
            code VARCHAR(10) PRIMARY KEY,
            district_code VARCHAR(10) REFERENCES districts(code),
            name TEXT NOT NULL,
            crawled_at TIMESTAMP DEFAULT NOW()
        );

        CREATE TABLE IF NOT EXISTS quarters (
            code VARCHAR(10) PRIMARY KEY,
            village_code VARCHAR(10) REFERENCES villages(code),
            name TEXT NOT NULL,
            crawled_at TIMESTAMP DEFAULT NOW()
        );

        CREATE TABLE IF NOT EXISTS streets (
            code VARCHAR(20) PRIMARY KEY,
            quarter_code VARCHAR(10) REFERENCES quarters(code),
            name TEXT,
            street_type TEXT,
            crawled_at TIMESTAMP DEFAULT NOW()
        );

        CREATE TABLE IF NOT EXISTS buildings (
            code VARCHAR(20) PRIMARY KEY,
            street_code VARCHAR(20) REFERENCES streets(code),
            outer_door_num TEXT,
            site_name TEXT,
            block_name TEXT,
            crawled_at TIMESTAMP DEFAULT NOW()
        );

        CREATE TABLE IF NOT EXISTS independent_sections (
            address_code VARCHAR(20) PRIMARY KEY,
            building_code VARCHAR(20) REFERENCES buildings(code),
            inner_door_num TEXT,
            crawled_at TIMESTAMP DEFAULT NOW()
        );

        -- Progress tracking
        CREATE TABLE IF NOT EXISTS crawl_progress (
            level TEXT NOT NULL,
            parent_code VARCHAR(20) NOT NULL,
            completed BOOLEAN DEFAULT FALSE,
            updated_at TIMESTAMP DEFAULT NOW(),
            PRIMARY KEY (level, parent_code)
        );
    """)

    conn.commit()
    cur.close()
    conn.close()
    print("✅ Database tables created.")


def upsert_cities(rows):
    """rows: list of (code, name)"""
    conn = get_connection()
    cur = conn.cursor()
    execute_values(cur, """
        INSERT INTO cities (code, name) VALUES %s
        ON CONFLICT (code) DO UPDATE SET name = EXCLUDED.name, crawled_at = NOW()
    """, rows)
    conn.commit()
    cur.close()
    conn.close()


def upsert_districts(rows):
    """rows: list of (code, city_code, name)"""
    conn = get_connection()
    cur = conn.cursor()
    execute_values(cur, """
        INSERT INTO districts (code, city_code, name) VALUES %s
        ON CONFLICT (code) DO UPDATE SET name = EXCLUDED.name, crawled_at = NOW()
    """, rows)
    conn.commit()
    cur.close()
    conn.close()


def upsert_villages(rows):
    """rows: list of (code, district_code, name)"""
    conn = get_connection()
    cur = conn.cursor()
    execute_values(cur, """
        INSERT INTO villages (code, district_code, name) VALUES %s
        ON CONFLICT (code) DO UPDATE SET name = EXCLUDED.name, crawled_at = NOW()
    """, rows)
    conn.commit()
    cur.close()
    conn.close()


def upsert_quarters(rows):
    """rows: list of (code, village_code, name)"""
    conn = get_connection()
    cur = conn.cursor()
    execute_values(cur, """
        INSERT INTO quarters (code, village_code, name) VALUES %s
        ON CONFLICT (code) DO UPDATE SET name = EXCLUDED.name, crawled_at = NOW()
    """, rows)
    conn.commit()
    cur.close()
    conn.close()


def upsert_streets(rows):
    """rows: list of (code, quarter_code, name, street_type)"""
    conn = get_connection()
    cur = conn.cursor()
    execute_values(cur, """
        INSERT INTO streets (code, quarter_code, name, street_type) VALUES %s
        ON CONFLICT (code) DO UPDATE SET name = EXCLUDED.name, crawled_at = NOW()
    """, rows)
    conn.commit()
    cur.close()
    conn.close()


def upsert_buildings(rows):
    """rows: list of (code, street_code, outer_door_num, site_name, block_name)"""
    conn = get_connection()
    cur = conn.cursor()
    execute_values(cur, """
        INSERT INTO buildings (code, street_code, outer_door_num, site_name, block_name) VALUES %s
        ON CONFLICT (code) DO UPDATE SET outer_door_num = EXCLUDED.outer_door_num, crawled_at = NOW()
    """, rows)
    conn.commit()
    cur.close()
    conn.close()


def upsert_sections(rows):
    """rows: list of (address_code, building_code, inner_door_num)"""
    conn = get_connection()
    cur = conn.cursor()
    execute_values(cur, """
        INSERT INTO independent_sections (address_code, building_code, inner_door_num) VALUES %s
        ON CONFLICT (address_code) DO UPDATE SET inner_door_num = EXCLUDED.inner_door_num, crawled_at = NOW()
    """, rows)
    conn.commit()
    cur.close()
    conn.close()


def mark_progress(level, parent_code):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO crawl_progress (level, parent_code, completed, updated_at)
        VALUES (%s, %s, TRUE, NOW())
        ON CONFLICT (level, parent_code) DO UPDATE SET completed = TRUE, updated_at = NOW()
    """, (level, parent_code))
    conn.commit()
    cur.close()
    conn.close()


def is_completed(level, parent_code):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        SELECT completed FROM crawl_progress WHERE level = %s AND parent_code = %s
    """, (level, parent_code))
    row = cur.fetchone()
    cur.close()
    conn.close()
    return row and row[0]
