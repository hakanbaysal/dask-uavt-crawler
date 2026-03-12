#!/usr/bin/env python3
"""
DASK UAVT Address Code Crawler — Entry Point.

Usage:
    python main.py              # Full crawl (resumes from checkpoint)
    python main.py --migrate    # Only run DB migrations
    python main.py --status     # Show crawl status
    python main.py --reset      # Clear checkpoint and start fresh
"""

from __future__ import annotations

import argparse
import sys

from src.client.dask_client import DaskClient
from src.client.html_parser import HtmlParser
from src.config import Config
from src.repository.db import Database
from src.repository.migrations import run_migrations
from src.services.crawler import Crawler, CrawlerError
from src.services.progress import ProgressTracker


def parse_args() -> argparse.Namespace:
    """Parse CLI arguments."""
    parser = argparse.ArgumentParser(
        description="DASK UAVT Address Code Crawler",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--migrate",
        action="store_true",
        help="Run database migrations only (create tables)",
    )
    parser.add_argument(
        "--status",
        action="store_true",
        help="Show current crawl status (checkpoint + DB counts)",
    )
    parser.add_argument(
        "--reset",
        action="store_true",
        help="Clear checkpoint file and start fresh",
    )
    return parser.parse_args()


def cmd_migrate(config: Config) -> None:
    """Run database migrations."""
    logger = config.setup_logging()
    logger.info("Running migrations...")
    run_migrations(config)
    logger.info("Done.")


def cmd_status(config: Config) -> None:
    """Show crawl status."""
    logger = config.setup_logging()

    # Checkpoint
    progress = ProgressTracker(config)
    checkpoint = progress.load()
    logger.info("Checkpoint: city=%d district=%d village=%d quarter=%d street=%d building=%d completed=%s",
                checkpoint.city_code, checkpoint.district_code, checkpoint.village_code,
                checkpoint.quarter_code, checkpoint.street_code, checkpoint.building_code,
                checkpoint.completed)

    # DB counts
    try:
        with Database(config) as db:
            counts = db.get_total_counts()
            logger.info("Database row counts:")
            for table, count in counts.items():
                logger.info("  %s: %d", table, count)
    except Exception as exc:
        logger.warning("Could not connect to DB: %s", exc)


def cmd_reset(config: Config) -> None:
    """Clear checkpoint."""
    logger = config.setup_logging()
    progress = ProgressTracker(config)
    progress.clear()
    logger.info("Checkpoint cleared. Next run will start fresh.")


def cmd_crawl(config: Config) -> None:
    """Run the full crawl."""
    logger = config.setup_logging()

    # Ensure tables exist
    run_migrations(config)

    with DaskClient(config) as client, Database(config) as db:
        parser = HtmlParser()
        progress = ProgressTracker(config)

        crawler = Crawler(
            config=config,
            client=client,
            db=db,
            parser=parser,
            progress=progress,
        )

        try:
            crawler.run()
        except CrawlerError as exc:
            logger.critical("Crawler failed: %s", exc)
            sys.exit(1)
        except KeyboardInterrupt:
            logger.warning("Interrupted by user. Progress saved via checkpoint.")
            sys.exit(130)


def main() -> None:
    """Application entry point."""
    args = parse_args()
    config = Config()

    if args.migrate:
        cmd_migrate(config)
    elif args.status:
        cmd_status(config)
    elif args.reset:
        cmd_reset(config)
    else:
        cmd_crawl(config)


if __name__ == "__main__":
    main()
