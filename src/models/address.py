"""Address data models for DASK UAVT hierarchy."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class City:
    """İl (Province) model."""

    code: int
    name: str

    def __str__(self) -> str:
        return f"City({self.code}, {self.name})"


@dataclass
class District:
    """İlçe (District) model."""

    code: int
    name: str
    city_code: int

    def __str__(self) -> str:
        return f"District({self.code}, {self.name})"


@dataclass
class Village:
    """Bucak/Köy (Village/Sub-district) model."""

    code: int
    name: str
    district_code: int

    def __str__(self) -> str:
        return f"Village({self.code}, {self.name})"


@dataclass
class Quarter:
    """Mahalle (Quarter/Neighbourhood) model."""

    code: int
    name: str
    village_code: int

    def __str__(self) -> str:
        return f"Quarter({self.code}, {self.name})"


@dataclass
class Street:
    """Cadde/Sokak (Street) model — parsed from HTML."""

    code: int
    name: str
    street_type: str
    quarter_code: int

    def __str__(self) -> str:
        return f"Street({self.code}, {self.street_type} {self.name})"


@dataclass
class Building:
    """Bina (Building) model — parsed from HTML."""

    code: int
    building_no: str
    building_code: str
    site_name: str
    building_name: str
    street_code: int

    def __str__(self) -> str:
        return f"Building({self.code}, No:{self.building_no})"


@dataclass
class Section:
    """İç Kapı / Bağımsız Bölüm (Unit/Section) model — parsed from HTML."""

    uavt_code: int
    door_no: str
    building_code: int

    def __str__(self) -> str:
        return f"Section(UAVT:{self.uavt_code}, Door:{self.door_no})"


@dataclass
class AddressVerification:
    """Adres Kodu Doğrulama sonucu."""

    uavt_code: int
    full_address: str
    verified: bool = False

    def __str__(self) -> str:
        status = "✓" if self.verified else "✗"
        return f"Address({status} {self.uavt_code})"
