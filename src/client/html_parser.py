"""HTML table parser for DASK UAVT responses (sf, dk, ick types)."""

from __future__ import annotations

import logging
import re
from typing import List

from bs4 import BeautifulSoup

from src.models.address import Building, Section, Street


class ParseError(Exception):
    """Raised when HTML parsing fails."""


class HtmlParser:
    """
    Parse HTML table responses from DASK API.

    Different type codes return different table structures:
    - sf (Street):   [type, name, onclick→id]
    - dk (Building): [building_no, building_code, site_name, building_name, onclick→id]
    - ick (Section): [door_no, onclick→uavt_code]
    """

    # Regex to extract numeric ID from onclick attributes like "ss('12345')", "sb('12345')", or "yl('12345')"
    ONCLICK_ID_PATTERN = re.compile(r"(?:yl|ss|sb)\(['\"]?(\d+)['\"]?\)")

    def __init__(self) -> None:
        self._logger = logging.getLogger("dask_uavt.parser")

    def _extract_onclick_id(self, element) -> int:
        """
        Extract numeric ID from an element's onclick attribute or row id.

        Args:
            element: BeautifulSoup Tag with onclick attribute or id like "s12345"/"d12345".

        Returns:
            Extracted integer ID.

        Raises:
            ParseError: If ID cannot be extracted.
        """
        # Try onclick attribute first
        onclick = element.get("onclick", "")
        if not onclick:
            link = element.find("a", onclick=True)
            if link:
                onclick = link.get("onclick", "")

        match = self.ONCLICK_ID_PATTERN.search(onclick)
        if match:
            return int(match.group(1))

        # Fallback: extract from row id attribute (e.g., "s1462035", "d91013881")
        row_id = element.get("id", "")
        if row_id:
            id_match = re.match(r"[a-z](\d+)", row_id)
            if id_match:
                return int(id_match.group(1))

        raise ParseError(f"Cannot extract ID from element: onclick='{onclick}', id='{element.get('id', '')}'")

    def _get_rows(self, html: str) -> list:
        """
        Parse HTML and return table rows (excluding header).

        Args:
            html: Raw HTML string.

        Returns:
            List of <tr> Tag objects.
        """
        # Try UTF-8 first, fall back to ISO-8859-9 for Turkish chars
        soup = BeautifulSoup(html, "html.parser")
        rows = soup.find_all("tr")

        # Skip header row if present
        if rows and rows[0].find("th"):
            rows = rows[1:]

        return rows

    def parse_streets(self, html: str, quarter_code: int) -> List[Street]:
        """
        Parse street (sf) HTML response.

        Table columns: [0] Type, [1] Name, [2] has onclick → ID

        Args:
            html: Raw HTML from sf type request.
            quarter_code: Parent quarter code.

        Returns:
            List of Street objects.
        """
        streets: List[Street] = []
        rows = self._get_rows(html)

        for row in rows:
            try:
                cols = row.find_all("td")
                if len(cols) < 2:
                    continue

                street_type = cols[0].get_text(strip=True)
                name = cols[1].get_text(strip=True)

                # ID is extracted from the onclick on the last column or the row itself
                try:
                    code = self._extract_onclick_id(cols[-1])
                except ParseError:
                    code = self._extract_onclick_id(row)

                streets.append(
                    Street(
                        code=code,
                        name=name,
                        street_type=street_type,
                        quarter_code=quarter_code,
                    )
                )

            except (ParseError, IndexError, ValueError) as exc:
                self._logger.warning(
                    "Skipping malformed street row (quarter=%d): %s", quarter_code, exc
                )

        self._logger.debug(
            "Parsed %d streets for quarter %d", len(streets), quarter_code
        )
        return streets

    def parse_buildings(self, html: str, street_code: int) -> List[Building]:
        """
        Parse building (dk) HTML response.

        Table columns: [0] Building No, [1] Building Code, [2] Site Name,
                        [3] Building Name, [4] has onclick → ID

        Args:
            html: Raw HTML from dk type request.
            street_code: Parent street code.

        Returns:
            List of Building objects.
        """
        buildings: List[Building] = []
        rows = self._get_rows(html)

        for row in rows:
            try:
                cols = row.find_all("td")
                if len(cols) < 4:
                    continue

                building_no = cols[0].get_text(strip=True)
                building_code = cols[1].get_text(strip=True)
                site_name = cols[2].get_text(strip=True) if len(cols) > 2 else ""
                building_name = cols[3].get_text(strip=True) if len(cols) > 3 else ""

                # ID from the last column's onclick
                try:
                    code = self._extract_onclick_id(cols[-1])
                except ParseError:
                    code = self._extract_onclick_id(row)

                buildings.append(
                    Building(
                        code=code,
                        building_no=building_no,
                        building_code=building_code,
                        site_name=site_name,
                        building_name=building_name,
                        street_code=street_code,
                    )
                )

            except (ParseError, IndexError, ValueError) as exc:
                self._logger.warning(
                    "Skipping malformed building row (street=%d): %s",
                    street_code, exc,
                )

        self._logger.debug(
            "Parsed %d buildings for street %d", len(buildings), street_code
        )
        return buildings

    def parse_sections(self, html: str, building_code: int) -> List[Section]:
        """
        Parse section/unit (ick) HTML response.

        Table columns: [0] Door No, [1] has onclick → UAVT code

        Args:
            html: Raw HTML from ick type request.
            building_code: Parent building code.

        Returns:
            List of Section objects.
        """
        sections: List[Section] = []
        rows = self._get_rows(html)

        for row in rows:
            try:
                cols = row.find_all("td")
                if len(cols) < 1:
                    continue

                door_no = cols[0].get_text(strip=True)

                # UAVT code from onclick
                try:
                    uavt_code = self._extract_onclick_id(cols[-1])
                except ParseError:
                    uavt_code = self._extract_onclick_id(row)

                sections.append(
                    Section(
                        uavt_code=uavt_code,
                        door_no=door_no,
                        building_code=building_code,
                    )
                )

            except (ParseError, IndexError, ValueError) as exc:
                self._logger.warning(
                    "Skipping malformed section row (building=%d): %s",
                    building_code, exc,
                )

        self._logger.debug(
            "Parsed %d sections for building %d", len(sections), building_code
        )
        return sections
