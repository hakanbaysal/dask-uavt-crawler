"""Tests for Crawler service — hierarchy traversal and checkpoint logic."""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch, call

import pytest

from src.client.dask_client import DaskClient
from src.client.html_parser import HtmlParser
from src.config import Config
from src.models.address import City, District, Village, Quarter, Street, Building, Section
from src.repository.db import Database
from src.services.crawler import Crawler, CrawlerError
from src.services.progress import Checkpoint, ProgressTracker


@pytest.fixture
def config() -> Config:
    """Test config with fast settings."""
    return Config(
        base_url="https://adreskodu.dask.gov.tr",
        request_delay=0.0,
        max_retries=1,
        retry_delay=0.0,
        request_timeout=5,
        checkpoint_dir="/tmp/test_checkpoints",
    )


@pytest.fixture
def mock_client() -> MagicMock:
    return MagicMock(spec=DaskClient)


@pytest.fixture
def mock_db() -> MagicMock:
    db = MagicMock(spec=Database)
    db.insert_cities.return_value = 0
    db.insert_districts.return_value = 0
    db.insert_villages.return_value = 0
    db.insert_quarters.return_value = 0
    db.insert_streets.return_value = 0
    db.insert_buildings.return_value = 0
    db.insert_sections.return_value = 0
    db.get_total_counts.return_value = {
        "cities": 1, "districts": 1, "villages": 1, "quarters": 1,
        "streets": 1, "buildings": 1, "sections": 1,
    }
    return db


@pytest.fixture
def mock_parser() -> MagicMock:
    return MagicMock(spec=HtmlParser)


@pytest.fixture
def mock_progress() -> MagicMock:
    progress = MagicMock(spec=ProgressTracker)
    progress.load.return_value = Checkpoint()
    return progress


@pytest.fixture
def crawler(config, mock_client, mock_db, mock_parser, mock_progress) -> Crawler:
    return Crawler(
        config=config,
        client=mock_client,
        db=mock_db,
        parser=mock_parser,
        progress=mock_progress,
    )


class TestParseJsonList:
    """Tests for JSON response parsing."""

    def test_parse_with_yt_wrapper(self, crawler: Crawler):
        """Should extract items from {"yt": [...]} wrapper."""
        raw = json.dumps({"yt": [{"value": "1", "text": "ADANA"}, {"value": "2", "text": "ADIYAMAN"}]})
        result = crawler._parse_json_list(raw)
        assert len(result) == 2
        assert result[0]["text"] == "ADANA"

    def test_parse_plain_array(self, crawler: Crawler):
        """Should handle bare JSON array."""
        raw = json.dumps([{"value": "1", "text": "TEST"}])
        result = crawler._parse_json_list(raw)
        assert len(result) == 1

    def test_parse_invalid_json(self, crawler: Crawler):
        """Should return empty list on invalid JSON."""
        result = crawler._parse_json_list("not json {{{")
        assert result == []

    def test_parse_empty_string(self, crawler: Crawler):
        """Empty string should return empty list."""
        result = crawler._parse_json_list("")
        assert result == []


class TestShouldSkip:
    """Tests for checkpoint skip logic."""

    def test_skip_when_code_before_checkpoint(self, crawler: Crawler):
        """Codes <= checkpoint should be skipped."""
        assert crawler._should_skip(code=5, checkpoint_code=10) is True
        assert crawler._should_skip(code=10, checkpoint_code=10) is True

    def test_no_skip_when_code_after_checkpoint(self, crawler: Crawler):
        """Codes > checkpoint should not be skipped."""
        assert crawler._should_skip(code=11, checkpoint_code=10) is False

    def test_no_skip_when_checkpoint_is_zero(self, crawler: Crawler):
        """Zero checkpoint means nothing to skip."""
        assert crawler._should_skip(code=1, checkpoint_code=0) is False


class TestCrawlerRun:
    """Integration tests for the run() method."""

    def test_run_fetches_cities_first(self, crawler, mock_client, mock_db):
        """Run should fetch cities as the first step."""
        mock_client.load.side_effect = [
            json.dumps({"yt": [{"value": "1", "text": "ADANA"}]}),  # cities
            json.dumps({"yt": []}),  # districts for ADANA
        ]

        crawler.run()

        mock_db.insert_cities.assert_called_once()
        cities = mock_db.insert_cities.call_args[0][0]
        assert len(cities) == 1
        assert cities[0].name == "ADANA"

    def test_run_skips_completed(self, crawler, mock_progress):
        """Should return immediately if checkpoint shows completed."""
        mock_progress.load.return_value = Checkpoint(completed=True)

        crawler.run()

        # Should not attempt any API calls
        crawler._client.load.assert_not_called()

    def test_run_traverses_hierarchy(self, crawler, mock_client, mock_db, mock_parser):
        """Should traverse city → district → village → quarter → street → building → section."""
        mock_client.load.side_effect = [
            json.dumps({"yt": [{"value": "1", "text": "ADANA"}]}),
            json.dumps({"yt": [{"value": "10", "text": "SEYHAN"}]}),
            json.dumps({"yt": [{"value": "100", "text": "MERKEZ"}]}),
            json.dumps({"yt": [{"value": "1000", "text": "REŞATBEY"}]}),
            "<table><tr><td>SOKAK</td><td>TEST</td><td onclick=\"yl('5000')\">Seç</td></tr></table>",
            "<table><tr><td>1</td><td>BN1</td><td></td><td></td><td onclick=\"yl('6000')\">Seç</td></tr></table>",
            "<table><tr><td>1</td><td onclick=\"yl('70000')\">Seç</td></tr></table>",
        ]

        # Parser mocks for HTML types
        mock_parser.parse_streets.return_value = [
            Street(code=5000, name="TEST", street_type="SOKAK", quarter_code=1000)
        ]
        mock_parser.parse_buildings.return_value = [
            Building(code=6000, building_no="1", building_code="BN1",
                     site_name="", building_name="", street_code=5000)
        ]
        mock_parser.parse_sections.return_value = [
            Section(uavt_code=70000, door_no="1", building_code=6000)
        ]

        crawler.run()

        # Verify all levels were inserted
        mock_db.insert_cities.assert_called_once()
        mock_db.insert_districts.assert_called_once()
        mock_db.insert_villages.assert_called_once()
        mock_db.insert_quarters.assert_called_once()
        mock_db.insert_streets.assert_called_once()
        mock_db.insert_buildings.assert_called_once()
        mock_db.insert_sections.assert_called_once()

    def test_run_saves_checkpoint_after_city(self, crawler, mock_client, mock_progress):
        """Progress should be saved after each city is processed."""
        mock_client.load.side_effect = [
            json.dumps({"yt": [{"value": "1", "text": "ADANA"}, {"value": "2", "text": "ADIYAMAN"}]}),
            json.dumps({"yt": []}),  # No districts for ADANA
            json.dumps({"yt": []}),  # No districts for ADIYAMAN
        ]

        crawler.run()

        # Progress should be saved at least for each city + final
        assert mock_progress.save.call_count >= 2


class TestCheckpointResume:
    """Tests for checkpoint-based resumption."""

    def test_resume_skips_completed_cities(self, crawler, mock_client, mock_progress):
        """Cities before checkpoint should be skipped."""
        mock_progress.load.return_value = Checkpoint(city_code=34)

        mock_client.load.side_effect = [
            json.dumps({"yt": [
                {"value": "1", "text": "ADANA"},
                {"value": "34", "text": "İSTANBUL"},
                {"value": "35", "text": "İZMİR"},
            ]}),
            json.dumps({"yt": []}),  # Districts for İZMİR
        ]

        crawler.run()

        # Only 2 load calls: cities + districts for İZMİR
        assert mock_client.load.call_count == 2
