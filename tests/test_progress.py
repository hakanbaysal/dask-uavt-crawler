"""Tests for ProgressTracker — checkpoint save/load/clear."""

from __future__ import annotations

import json
import os
import tempfile

import pytest

from src.config import Config
from src.services.progress import Checkpoint, ProgressTracker


@pytest.fixture
def tmp_dir():
    """Return a temporary directory for checkpoints."""
    with tempfile.TemporaryDirectory() as d:
        yield d


@pytest.fixture
def config(tmp_dir) -> Config:
    return Config(checkpoint_dir=tmp_dir)


@pytest.fixture
def tracker(config) -> ProgressTracker:
    return ProgressTracker(config)


class TestCheckpoint:
    """Tests for Checkpoint dataclass."""

    def test_default_values(self):
        cp = Checkpoint()
        assert cp.city_code == 0
        assert cp.district_code == 0
        assert cp.completed is False

    def test_reset_below_city(self):
        cp = Checkpoint(city_code=34, district_code=10, village_code=5,
                        quarter_code=3, street_code=2, building_code=1)
        cp.reset_below_city()
        assert cp.city_code == 34  # unchanged
        assert cp.district_code == 0
        assert cp.village_code == 0
        assert cp.quarter_code == 0
        assert cp.street_code == 0
        assert cp.building_code == 0

    def test_reset_below_district(self):
        cp = Checkpoint(district_code=10, village_code=5, quarter_code=3,
                        street_code=2, building_code=1)
        cp.reset_below_district()
        assert cp.district_code == 10  # unchanged
        assert cp.village_code == 0
        assert cp.building_code == 0

    def test_reset_below_village(self):
        cp = Checkpoint(village_code=5, quarter_code=3, street_code=2, building_code=1)
        cp.reset_below_village()
        assert cp.village_code == 5
        assert cp.quarter_code == 0

    def test_reset_below_quarter(self):
        cp = Checkpoint(quarter_code=3, street_code=2, building_code=1)
        cp.reset_below_quarter()
        assert cp.quarter_code == 3
        assert cp.street_code == 0
        assert cp.building_code == 0

    def test_reset_below_street(self):
        cp = Checkpoint(street_code=2, building_code=1)
        cp.reset_below_street()
        assert cp.street_code == 2
        assert cp.building_code == 0


class TestProgressTracker:
    """Tests for ProgressTracker — file-based checkpoint persistence."""

    def test_load_returns_fresh_when_no_file(self, tracker):
        """Should return default checkpoint when no file exists."""
        cp = tracker.load()
        assert cp.city_code == 0
        assert cp.completed is False

    def test_save_and_load_roundtrip(self, tracker):
        """Saved checkpoint should be loadable."""
        cp = Checkpoint(city_code=34, district_code=500, completed=False)
        tracker.save(cp)

        loaded = tracker.load()
        assert loaded.city_code == 34
        assert loaded.district_code == 500
        assert loaded.completed is False

    def test_save_creates_json_file(self, tracker, tmp_dir):
        """Save should create a checkpoint.json file."""
        cp = Checkpoint(city_code=1)
        tracker.save(cp)

        filepath = os.path.join(tmp_dir, "checkpoint.json")
        assert os.path.exists(filepath)

        with open(filepath, "r") as f:
            data = json.load(f)
        assert data["city_code"] == 1

    def test_clear_removes_file(self, tracker, tmp_dir):
        """Clear should delete the checkpoint file."""
        cp = Checkpoint(city_code=1)
        tracker.save(cp)

        filepath = os.path.join(tmp_dir, "checkpoint.json")
        assert os.path.exists(filepath)

        tracker.clear()
        assert not os.path.exists(filepath)

    def test_clear_when_no_file_exists(self, tracker):
        """Clear should not raise when no file exists."""
        tracker.clear()  # should not raise

    def test_load_corrupted_file(self, tracker, tmp_dir):
        """Corrupted file should return fresh checkpoint."""
        filepath = os.path.join(tmp_dir, "checkpoint.json")
        with open(filepath, "w") as f:
            f.write("not json {{{")

        cp = tracker.load()
        assert cp.city_code == 0

    def test_save_overwrites_existing(self, tracker):
        """Subsequent saves should overwrite."""
        tracker.save(Checkpoint(city_code=1))
        tracker.save(Checkpoint(city_code=99))

        loaded = tracker.load()
        assert loaded.city_code == 99


class TestConfig:
    """Tests for Config defaults and properties."""

    def test_default_values(self):
        config = Config()
        assert config.base_url == "https://adreskodu.dask.gov.tr"
        assert config.db_port == 5432
        assert config.request_delay == 1.0
        assert config.max_retries == 3

    def test_db_dsn_property(self):
        config = Config(db_host="myhost", db_port=5433, db_name="testdb",
                        db_user="admin", db_password="secret")
        dsn = config.db_dsn
        assert "myhost" in dsn
        assert "5433" in dsn
        assert "testdb" in dsn
        assert "admin" in dsn
        assert "secret" in dsn

    def test_setup_logging_returns_logger(self):
        config = Config(log_level="DEBUG")
        logger = config.setup_logging()
        assert logger.name == "dask_uavt"
        assert logger.level == 10  # DEBUG

    def test_setup_logging_idempotent(self):
        """Calling setup_logging twice should not duplicate handlers."""
        config = Config()
        logger1 = config.setup_logging()
        handler_count = len(logger1.handlers)
        logger2 = config.setup_logging()
        assert len(logger2.handlers) == handler_count


class TestModels:
    """Tests for address model __str__ methods."""

    def test_city_str(self):
        from src.models.address import City
        assert "ADANA" in str(City(code=1, name="ADANA"))

    def test_district_str(self):
        from src.models.address import District
        assert "SEYHAN" in str(District(code=10, name="SEYHAN", city_code=1))

    def test_village_str(self):
        from src.models.address import Village
        assert "MERKEZ" in str(Village(code=100, name="MERKEZ", district_code=10))

    def test_quarter_str(self):
        from src.models.address import Quarter
        assert "REŞATBEY" in str(Quarter(code=1000, name="REŞATBEY", village_code=100))

    def test_street_str(self):
        from src.models.address import Street
        s = Street(code=5000, name="ATATÜRK", street_type="SOKAK", quarter_code=1000)
        assert "SOKAK" in str(s)
        assert "ATATÜRK" in str(s)

    def test_building_str(self):
        from src.models.address import Building
        b = Building(code=6000, building_no="15", building_code="BN1",
                     site_name="", building_name="", street_code=5000)
        assert "15" in str(b)

    def test_section_str(self):
        from src.models.address import Section
        s = Section(uavt_code=70000, door_no="3", building_code=6000)
        assert "70000" in str(s)
        assert "3" in str(s)

    def test_address_verification_str(self):
        from src.models.address import AddressVerification
        v = AddressVerification(uavt_code=70000, full_address="Test", verified=True)
        assert "✓" in str(v)
        v2 = AddressVerification(uavt_code=70000, full_address="Test", verified=False)
        assert "✗" in str(v2)
