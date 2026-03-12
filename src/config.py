"""Configuration module for DASK UAVT Crawler."""

import os
import logging
from dataclasses import dataclass, field


@dataclass
class Config:
    """Application configuration loaded from environment variables."""

    # DASK API
    base_url: str = field(
        default_factory=lambda: os.getenv("DASK_BASE_URL", "https://adreskodu.dask.gov.tr")
    )

    # Database
    db_host: str = field(default_factory=lambda: os.getenv("DB_HOST", "localhost"))
    db_port: int = field(default_factory=lambda: int(os.getenv("DB_PORT", "5432")))
    db_name: str = field(default_factory=lambda: os.getenv("DB_NAME", "dask_uavt"))
    db_user: str = field(default_factory=lambda: os.getenv("DB_USER", "postgres"))
    db_password: str = field(default_factory=lambda: os.getenv("DB_PASSWORD", "postgres"))

    # Crawler settings
    request_delay: float = field(
        default_factory=lambda: float(os.getenv("REQUEST_DELAY", "1.0"))
    )
    max_retries: int = field(
        default_factory=lambda: int(os.getenv("MAX_RETRIES", "3"))
    )
    retry_delay: float = field(
        default_factory=lambda: float(os.getenv("RETRY_DELAY", "5.0"))
    )
    request_timeout: int = field(
        default_factory=lambda: int(os.getenv("REQUEST_TIMEOUT", "30"))
    )

    # Logging
    log_level: str = field(
        default_factory=lambda: os.getenv("LOG_LEVEL", "INFO")
    )

    # Checkpoint
    checkpoint_dir: str = field(
        default_factory=lambda: os.getenv("CHECKPOINT_DIR", "checkpoints")
    )

    # Crawl scope (optional filters)
    start_city_code: int = field(
        default_factory=lambda: int(os.getenv("START_CITY_CODE", "0"))
    )
    end_city_code: int = field(
        default_factory=lambda: int(os.getenv("END_CITY_CODE", "0"))
    )

    @property
    def db_dsn(self) -> str:
        """Return PostgreSQL connection string."""
        return (
            f"host={self.db_host} port={self.db_port} dbname={self.db_name} "
            f"user={self.db_user} password={self.db_password}"
        )

    def setup_logging(self) -> logging.Logger:
        """Configure and return the application logger."""
        logger = logging.getLogger("dask_uavt")
        logger.setLevel(getattr(logging, self.log_level.upper(), logging.INFO))

        if not logger.handlers:
            handler = logging.StreamHandler()
            formatter = logging.Formatter(
                "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
                datefmt="%Y-%m-%d %H:%M:%S",
            )
            handler.setFormatter(formatter)
            logger.addHandler(handler)

        return logger
