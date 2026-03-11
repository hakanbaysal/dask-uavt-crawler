"""DASK UAVT Address Code Crawler"""
import json
import re
import time
import requests
from src.config import DASK_BASE_URL, DASK_ADDRESS_PAGE, REQUEST_DELAY, MAX_RETRIES
from src.captcha import solve_recaptcha
from src.db import (
    init_db, upsert_cities, upsert_districts, upsert_villages,
    upsert_quarters, upsert_streets, upsert_buildings, upsert_sections,
    mark_progress, is_completed
)


class DaskCrawler:
    def __init__(self, dry_run=False):
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36",
            "Referer": DASK_ADDRESS_PAGE,
        })
        self.csrf_token = None
        self.dry_run = dry_run

    def _init_session(self):
        """Get CSRF token from the address page."""
        resp = self.session.get(DASK_ADDRESS_PAGE)
        resp.raise_for_status()
        match = re.search(
            r'name="__RequestVerificationToken".*?value="([^"]+)"', resp.text
        )
        if not match:
            raise RuntimeError("Could not extract CSRF token")
        self.csrf_token = match.group(1)
        print(f"🔒 CSRF token acquired: {self.csrf_token[:20]}...")

    def _validate_captcha(self):
        """Solve and validate reCAPTCHA."""
        captcha_response = solve_recaptcha()
        resp = self.session.post(
            f"{DASK_BASE_URL}/tr/AddressCode/ValidateCaptcha",
            data={
                "gRecaptchaResponse": captcha_response,
                "__RequestVerificationToken": self.csrf_token,
            },
        )
        result = resp.text.strip().strip('"')
        if result == "validCaptcha":
            print("✅ CAPTCHA validated!")
            return True
        else:
            print(f"❌ CAPTCHA validation failed: {result}")
            return False

    def _post(self, endpoint, data=None, retry=0):
        """POST to DASK API with retry and captcha handling."""
        if data is None:
            data = {}
        data["__RequestVerificationToken"] = self.csrf_token

        time.sleep(REQUEST_DELAY)

        resp = self.session.post(f"{DASK_BASE_URL}{endpoint}", data=data)
        resp.raise_for_status()

        text = resp.text.strip()

        # Handle captcha trigger
        if '"showCaptcha"' in text or text == '"showCaptcha"':
            if retry >= MAX_RETRIES:
                raise RuntimeError(f"Max retries reached for {endpoint}")
            print(f"⚠️ Captcha triggered on {endpoint}, re-solving...")
            self._validate_captcha()
            return self._post(endpoint, data, retry + 1)

        try:
            return json.loads(text)
        except json.JSONDecodeError:
            # Some endpoints return HTML tables (streets, buildings, doors)
            return text

    def get_cities(self):
        """Fetch all cities (iller)."""
        print("\n📍 Fetching cities...")
        data = self._post("/tr/AddressCode/Cities")
        if isinstance(data, list):
            print(f"   Found {len(data)} cities")
            return data
        return []

    def get_districts(self, city_code):
        """Fetch districts for a city."""
        data = self._post("/tr/AddressCode/Districts", {"cityCode": city_code})
        if isinstance(data, list):
            return data
        return []

    def get_villages(self, district_code):
        """Fetch villages/townships for a district."""
        data = self._post("/tr/AddressCode/Villages", {"districtCode": district_code})
        if isinstance(data, list):
            return data
        return []

    def get_quarters(self, village_code):
        """Fetch quarters (mahalle) for a village."""
        data = self._post("/tr/AddressCode/Quarters", {"villageCode": village_code})
        if isinstance(data, list):
            return data
        return []

    def get_streets(self, quarter_code):
        """Fetch streets for a quarter."""
        data = self._post("/tr/AddressCode/Streets", {"quarterCode": quarter_code})
        if isinstance(data, list):
            return data
        return []

    def get_buildings(self, street_code):
        """Fetch buildings for a street."""
        data = self._post("/tr/AddressCode/Buildings", {"streetCode": street_code})
        if isinstance(data, list):
            return data
        return []

    def get_sections(self, building_code):
        """Fetch independent sections (iç kapı) for a building."""
        data = self._post("/tr/AddressCode/IndependentSections", {"buildingCode": building_code})
        if isinstance(data, list):
            return data
        return []

    def start(self):
        """Initialize session, solve captcha, start crawling."""
        print("🚀 DASK UAVT Crawler starting...")

        if not self.dry_run:
            init_db()

        self._init_session()

        if not self._validate_captcha():
            raise RuntimeError("Failed to validate captcha")

        # Crawl hierarchy
        cities = self.get_cities()
        if not cities:
            print("❌ No cities returned!")
            return

        if self.dry_run:
            print(f"\n🧪 DRY RUN — showing first 3 cities:")
            for c in cities[:3]:
                print(f"   {c.get('code')} - {c.get('nameText', c.get('cityNameText', '?'))}")

            # Try one district fetch
            first_city = cities[0]
            districts = self.get_districts(first_city["code"])
            print(f"\n   Districts of {first_city.get('nameText', '?')}: {len(districts)}")
            for d in districts[:5]:
                print(f"   {d.get('code')} - {d.get('districtNameText', d.get('nameText', '?'))}")

            if districts:
                villages = self.get_villages(districts[0]["code"])
                print(f"\n   Villages of first district: {len(villages)}")
                for v in villages[:5]:
                    print(f"   {v.get('code')} - {v.get('townshipVillageNameText', v.get('nameText', '?'))}")

            print("\n✅ Dry run complete!")
            return

        # Full crawl
        if not self.dry_run:
            self._crawl_full(cities)

    def _crawl_full(self, cities):
        """Full hierarchical crawl."""
        rows = [(c["code"], c.get("nameText", c.get("cityNameText", ""))) for c in cities]
        upsert_cities(rows)

        for city in cities:
            city_code = city["code"]
            city_name = city.get("nameText", city.get("cityNameText", ""))

            if is_completed("city", city_code):
                print(f"⏭️ Skipping city {city_name} (already done)")
                continue

            print(f"\n🏙️ Crawling city: {city_name} ({city_code})")
            districts = self.get_districts(city_code)
            if districts:
                rows = [(d["code"], city_code, d.get("districtNameText", d.get("nameText", ""))) for d in districts]
                upsert_districts(rows)

            for district in districts:
                dist_code = district["code"]
                dist_name = district.get("districtNameText", district.get("nameText", ""))

                if is_completed("district", dist_code):
                    continue

                print(f"  📍 District: {dist_name}")
                villages = self.get_villages(dist_code)
                if villages:
                    rows = [(v["code"], dist_code, v.get("townshipVillageNameText", v.get("nameText", ""))) for v in villages]
                    upsert_villages(rows)

                for village in villages:
                    vil_code = village["code"]

                    if is_completed("village", vil_code):
                        continue

                    quarters = self.get_quarters(vil_code)
                    if quarters:
                        rows = [(q["code"], vil_code, q.get("nameText", "")) for q in quarters]
                        upsert_quarters(rows)

                    for quarter in quarters:
                        q_code = quarter["code"]

                        if is_completed("quarter", q_code):
                            continue

                        streets = self.get_streets(q_code)
                        if isinstance(streets, list) and streets:
                            rows = [(s["code"], q_code,
                                     s.get("nameText", s.get("streetNameText", "")),
                                     s.get("streetTypeExplanation", "")) for s in streets]
                            upsert_streets(rows)

                            for street in streets:
                                s_code = street["code"]

                                if is_completed("street", s_code):
                                    continue

                                buildings = self.get_buildings(s_code)
                                if isinstance(buildings, list) and buildings:
                                    rows = [(b["code"], s_code,
                                             b.get("outerDoorNum", ""),
                                             b.get("siteName", ""),
                                             b.get("blockName", "")) for b in buildings]
                                    upsert_buildings(rows)

                                    for building in buildings:
                                        b_code = building["code"]

                                        if is_completed("building", b_code):
                                            continue

                                        sections = self.get_sections(b_code)
                                        if isinstance(sections, list) and sections:
                                            rows = [(sec.get("addressNum", sec.get("code", "")),
                                                     b_code,
                                                     sec.get("innerDoorNum", "")) for sec in sections]
                                            upsert_sections(rows)

                                        mark_progress("building", b_code)

                                mark_progress("street", s_code)

                        mark_progress("quarter", q_code)

                    mark_progress("village", vil_code)

                mark_progress("district", dist_code)

            mark_progress("city", city_code)

        print("\n🎉 Full crawl complete!")


if __name__ == "__main__":
    import sys
    dry_run = "--dry-run" in sys.argv
    crawler = DaskCrawler(dry_run=dry_run)
    crawler.start()
