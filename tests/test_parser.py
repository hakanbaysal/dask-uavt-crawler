"""Tests for HtmlParser — street, building, and section parsing."""

from __future__ import annotations

import pytest

from src.client.html_parser import HtmlParser


@pytest.fixture
def parser() -> HtmlParser:
    """Return an HtmlParser instance."""
    return HtmlParser()


class TestParseStreets:
    """Tests for parse_streets()."""

    def test_parse_single_street(self, parser: HtmlParser):
        """Should parse a single street row correctly."""
        html = """
        <table>
            <tr><th>Tür</th><th>Ad</th><th>Seç</th></tr>
            <tr>
                <td>SOKAK</td>
                <td>ATATÜRK</td>
                <td><a onclick="yl('12345')">Seç</a></td>
            </tr>
        </table>
        """
        streets = parser.parse_streets(html, quarter_code=100)

        assert len(streets) == 1
        assert streets[0].code == 12345
        assert streets[0].name == "ATATÜRK"
        assert streets[0].street_type == "SOKAK"
        assert streets[0].quarter_code == 100

    def test_parse_multiple_streets(self, parser: HtmlParser):
        """Should parse multiple rows."""
        html = """
        <table>
            <tr>
                <td>CADDE</td>
                <td>BAĞDAT CADDESİ</td>
                <td><a onclick="yl('111')">Seç</a></td>
            </tr>
            <tr>
                <td>SOKAK</td>
                <td>GÜL SOKAK</td>
                <td><a onclick="yl('222')">Seç</a></td>
            </tr>
        </table>
        """
        streets = parser.parse_streets(html, quarter_code=50)

        assert len(streets) == 2
        assert streets[0].code == 111
        assert streets[1].code == 222

    def test_parse_empty_html(self, parser: HtmlParser):
        """Empty HTML should return empty list."""
        streets = parser.parse_streets("", quarter_code=1)
        assert streets == []

    def test_parse_malformed_row_skipped(self, parser: HtmlParser):
        """Rows without proper onclick should be skipped."""
        html = """
        <table>
            <tr><td>SOKAK</td><td>BROKEN</td><td>no onclick</td></tr>
            <tr>
                <td>CADDE</td>
                <td>OK STREET</td>
                <td><a onclick="yl('999')">Seç</a></td>
            </tr>
        </table>
        """
        streets = parser.parse_streets(html, quarter_code=1)

        assert len(streets) == 1
        assert streets[0].code == 999


class TestParseBuildings:
    """Tests for parse_buildings()."""

    def test_parse_single_building(self, parser: HtmlParser):
        """Should parse building with all columns."""
        html = """
        <table>
            <tr><th>No</th><th>Kod</th><th>Site</th><th>Ad</th><th>Seç</th></tr>
            <tr>
                <td>15</td>
                <td>BN-001</td>
                <td>GÜNEŞ SİTESİ</td>
                <td>A BLOK</td>
                <td><a onclick="yl('55555')">Seç</a></td>
            </tr>
        </table>
        """
        buildings = parser.parse_buildings(html, street_code=200)

        assert len(buildings) == 1
        b = buildings[0]
        assert b.code == 55555
        assert b.building_no == "15"
        assert b.building_code == "BN-001"
        assert b.site_name == "GÜNEŞ SİTESİ"
        assert b.building_name == "A BLOK"
        assert b.street_code == 200

    def test_parse_building_empty_optional_fields(self, parser: HtmlParser):
        """Should handle empty site/building name."""
        html = """
        <table>
            <tr>
                <td>3</td>
                <td>BN-002</td>
                <td></td>
                <td></td>
                <td><a onclick="yl('66666')">Seç</a></td>
            </tr>
        </table>
        """
        buildings = parser.parse_buildings(html, street_code=300)

        assert len(buildings) == 1
        assert buildings[0].site_name == ""
        assert buildings[0].building_name == ""

    def test_parse_buildings_empty_html(self, parser: HtmlParser):
        """Empty HTML should return empty list."""
        buildings = parser.parse_buildings("", street_code=1)
        assert buildings == []


class TestParseSections:
    """Tests for parse_sections()."""

    def test_parse_single_section(self, parser: HtmlParser):
        """Should parse section with door number and UAVT code."""
        html = """
        <table>
            <tr><th>Kapı No</th><th>Seç</th></tr>
            <tr>
                <td>3</td>
                <td><a onclick="yl('9876543')">Seç</a></td>
            </tr>
        </table>
        """
        sections = parser.parse_sections(html, building_code=500)

        assert len(sections) == 1
        assert sections[0].uavt_code == 9876543
        assert sections[0].door_no == "3"
        assert sections[0].building_code == 500

    def test_parse_multiple_sections(self, parser: HtmlParser):
        """Should parse multiple section rows."""
        html = """
        <table>
            <tr>
                <td>1</td>
                <td><a onclick="yl('100')">Seç</a></td>
            </tr>
            <tr>
                <td>2</td>
                <td><a onclick="yl('200')">Seç</a></td>
            </tr>
            <tr>
                <td>3</td>
                <td><a onclick="yl('300')">Seç</a></td>
            </tr>
        </table>
        """
        sections = parser.parse_sections(html, building_code=1)

        assert len(sections) == 3
        assert [s.uavt_code for s in sections] == [100, 200, 300]
        assert [s.door_no for s in sections] == ["1", "2", "3"]

    def test_parse_sections_empty(self, parser: HtmlParser):
        """Empty HTML should return empty list."""
        sections = parser.parse_sections("", building_code=1)
        assert sections == []


class TestOnclickExtraction:
    """Tests for onclick ID regex extraction."""

    def test_extract_with_single_quotes(self, parser: HtmlParser):
        """Should extract ID from yl('12345')."""
        from bs4 import BeautifulSoup

        html = '<td><a onclick="yl(\'12345\')">Seç</a></td>'
        soup = BeautifulSoup(html, "html.parser")
        td = soup.find("td")

        result = parser._extract_onclick_id(td)
        assert result == 12345

    def test_extract_with_double_quotes(self, parser: HtmlParser):
        """Should extract ID from yl("67890")."""
        from bs4 import BeautifulSoup

        html = '<td onclick="yl(&quot;67890&quot;)">Seç</td>'
        soup = BeautifulSoup(html, "html.parser")
        td = soup.find("td")

        result = parser._extract_onclick_id(td)
        assert result == 67890

    def test_extract_without_quotes(self, parser: HtmlParser):
        """Should extract ID from yl(12345)."""
        from bs4 import BeautifulSoup

        html = '<td onclick="yl(12345)">Seç</td>'
        soup = BeautifulSoup(html, "html.parser")
        td = soup.find("td")

        result = parser._extract_onclick_id(td)
        assert result == 12345
