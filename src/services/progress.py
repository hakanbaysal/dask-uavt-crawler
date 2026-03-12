"""Progress tracking — checkpoint-based resume for the crawler."""

from __future__ import annotations

import json
import logging
import os
from dataclasses import asdict, dataclass, field
from typing import Optional

from src.config import Config


@dataclass
class Checkpoint:
    """
    Tracks crawling progress at every hierarchy level.

    When the crawler finishes processing a node at any level,
    it stores that node's code here. On restart, the crawler
    skips all nodes up to and including the checkpointed one.
    """

    city_code: int = 0
    district_code: int = 0
    village_code: int = 0
    quarter_code: int = 0
    street_code: int = 0
    building_code: int = 0
    # Completed flags (set True when all children of a level are done)
    completed: bool = False

    def reset_below_city(self) -> None:
        """Reset all levels below city (when moving to next city)."""
        self.district_code = 0
        self.village_code = 0
        self.quarter_code = 0
        self.street_code = 0
        self.building_code = 0

    def reset_below_district(self) -> None:
        """Reset all levels below district."""
        self.village_code = 0
        self.quarter_code = 0
        self.street_code = 0
        self.building_code = 0

    def reset_below_village(self) -> None:
        """Reset all levels below village."""
        self.quarter_code = 0
        self.street_code = 0
        self.building_code = 0

    def reset_below_quarter(self) -> None:
        """Reset all levels below quarter."""
        self.street_code = 0
        self.building_code = 0

    def reset_below_street(self) -> None:
        """Reset all levels below street."""
        self.building_code = 0


class ProgressTracker:
    """
    Persists checkpoint to disk (JSON file) so the crawler
    can resume after crashes or interruptions.
    """

    CHECKPOINT_FILE = "checkpoint.json"

    def __init__(self, config: Config) -> None:
        self._config = config
        self._logger = logging.getLogger("dask_uavt.progress")
        self._dir = config.checkpoint_dir
        self._filepath = os.path.join(self._dir, self.CHECKPOINT_FILE)
        self._checkpoint: Optional[Checkpoint] = None

    def _ensure_dir(self) -> None:
        """Create checkpoint directory if it doesn't exist."""
        os.makedirs(self._dir, exist_ok=True)

    def load(self) -> Checkpoint:
        """
        Load checkpoint from disk or return a fresh one.

        Returns:
            Checkpoint instance.
        """
        self._ensure_dir()

        if os.path.exists(self._filepath):
            try:
                with open(self._filepath, "r", encoding="utf-8") as f:
                    data = json.load(f)
                self._checkpoint = Checkpoint(**data)
                self._logger.info(
                    "Checkpoint loaded — resuming from city=%d, district=%d",
                    self._checkpoint.city_code,
                    self._checkpoint.district_code,
                )
                return self._checkpoint
            except (json.JSONDecodeError, TypeError, KeyError) as exc:
                self._logger.warning(
                    "Corrupted checkpoint file, starting fresh: %s", exc
                )

        self._checkpoint = Checkpoint()
        return self._checkpoint

    def save(self, checkpoint: Checkpoint) -> None:
        """
        Persist checkpoint to disk.

        Args:
            checkpoint: Current progress state.
        """
        self._ensure_dir()
        self._checkpoint = checkpoint

        with open(self._filepath, "w", encoding="utf-8") as f:
            json.dump(asdict(checkpoint), f, indent=2)

        self._logger.debug(
            "Checkpoint saved — city=%d, district=%d, village=%d",
            checkpoint.city_code,
            checkpoint.district_code,
            checkpoint.village_code,
        )

    def clear(self) -> None:
        """Remove checkpoint file (crawl completed successfully)."""
        if os.path.exists(self._filepath):
            os.remove(self._filepath)
            self._logger.info("Checkpoint cleared — crawl complete.")
