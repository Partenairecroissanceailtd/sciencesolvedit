"""
Awin affiliate network adapter.
API docs: https://wiki.awin.com/index.php/API
"""

from __future__ import annotations
import logging, hashlib, time
from typing import Optional
import requests

from config import AffiliateOffer, NetworkCredentials, logger

API_BASE = "https://api.awin.com"


class AwinAdapter:
    """Fetch offers/programs from Awin API."""

    def __init__(self, credentials: NetworkCredentials):
        self.api_key = credentials.api_key
        self.publisher_id = credentials.publisher_id
        self.session = requests.Session()
        self.session.headers.update({
            "Authorization": f"Bearer {self.api_key}",
            "Accept": "application/json",
        })

    def test_auth(self) -> bool:
        """Verify credentials are valid."""
        try:
            r = self.session.get(f"{API_BASE}/accounts", timeout=10)
            return r.status_code == 200
        except Exception as e:
            logger.error(f"Awin auth test failed: {e}")
            return False

    def fetch_programs(self, category: str = "") -> list[dict]:
        """Get all available programs for our publisher account."""
        params = {}
        if category:
            params["category"] = category
        r = self.session.get(
            f"{API_BASE}/publishers/{self.publisher_id}/programmes",
            params=params, timeout=30
        )
        r.raise_for_status()
        return r.json()

    def fetch_commission_groups(self, program_id: int) -> list[dict]:
        """Fetch commission tiers for a specific program."""
        r = self.session.get(
            f"{API_BASE}/publishers/{self.publisher_id}/programmes/{program_id}/commissiongroups",
            timeout=15
        )
        r.raise_for_status()
        return r.json()

    def generate_deeplink(self, program_id: int, destination_url: str) -> str:
        """Create an Awin tracking deep link."""
        params = {
            "publisherId": self.publisher_id,
            "advertiserId": program_id,
            "destinationUrl": destination_url,
        }
        r = self.session.get(
            f"{API_BASE}/publishers/{self.publisher_id}/deeplink",
            params=params, timeout=10
        )
        r.raise_for_status()
        return r.text.strip()

    def search_programs(self, query: str) -> list[dict]:
        """Search programs by keyword."""
        r = self.session.get(
            f"{API_BASE}/publishers/{self.publisher_id}/programmes",
            params={"search": query}, timeout=30
        )
        r.raise_for_status()
        return r.json()

    def to_offer(self, program: dict) -> Optional[AffiliateOffer]:
        """Convert raw Awin program data to normalized Offer."""
        try:
            category = self._map_category(program.get("category", {}).get("id", ""))
            return AffiliateOffer(
                network="awin",
                offer_id=str(program.get("id", "")),
                program_name=program.get("name", ""),
                advertiser=program.get("advertiser", {}).get("name", ""),
                description=program.get("description", ""),
                category=category,
                commission_type=program.get("commissionType", "percentage"),
                commission_value=float(program.get("commissionRange", "0").split("-")[0]),
                cookie_days=int(program.get("cookieDays", 30)),
                payout_model="sale",
                geo_targets=program.get("validCountries", ["US"]),
                merchant_logo=program.get("logoUrl", ""),
                merchant_rating=float(program.get("rating", 0)),
                raw_data=program,
            )
        except Exception as e:
            logger.warning(f"Failed to convert Awin program: {e}")
            return None

    def _map_category(self, awin_cat: str) -> str:
        """Map Awin category ID to our niche taxonomy."""
        mapping = {
            "health-beauty": "biohacking",
            "sport-fitness": "wearables",
            "electronics": "wearables",
            "home-garden": "sauna",
            "medical": "red-light-therapy",
        }
        return mapping.get(awin_cat.lower(), "biohacking")
