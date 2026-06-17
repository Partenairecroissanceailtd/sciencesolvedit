"""
PartnerStack affiliate network adapter.
API docs: https://developers.partnerstack.com/
"""

from __future__ import annotations
import logging, base64
from typing import Optional
import requests

from .config import AffiliateOffer, NetworkCredentials, logger


class PartnerStackAdapter:
    """Fetch offers/partnerships from PartnerStack API."""

    def __init__(self, credentials: NetworkCredentials):
        self.api_key = credentials.api_key
        self.api_secret = credentials.api_secret
        self.session = requests.Session()
        # Basic auth with API key + secret
        auth_str = f"{self.api_key}:{self.api_secret}"
        b64 = base64.b64encode(auth_str.encode()).decode()
        self.session.headers.update({
            "Authorization": f"Basic {b64}",
            "Accept": "application/json",
        })

    def test_auth(self) -> bool:
        """Verify credentials by listing a resource."""
        try:
            r = self.session.get(
                "https://api.partnerstack.com/v1/",
                timeout=10
            )
            return r.status_code == 200
        except Exception as e:
            logger.error(f"PartnerStack auth test failed: {e}")
            return False

    def fetch_offers(self, params: dict = None) -> list[dict]:
        """List available offers/partnerships."""
        if params is None:
            params = {"limit": 100}
        r = self.session.get(
            "https://api.partnerstack.com/v1/offers",
            params=params, timeout=30
        )
        r.raise_for_status()
        data = r.json()
        return data.get("data", data.get("results", []))

    def fetch_programs(self) -> list[dict]:
        """Get all partnership programs."""
        r = self.session.get(
            "https://api.partnerstack.com/v1/partnerships",
            params={"limit": 100}, timeout=30
        )
        r.raise_for_status()
        data = r.json()
        return data.get("data", data.get("results", []))

    def generate_tracking_link(
        self, offer_id: str, destination_url: str, campaign: str = ""
    ) -> str:
        """Generate a PartnerStack tracking link for an offer."""
        params = {
            "offer_id": offer_id,
            "url": destination_url,
            "campaign": campaign or "sciencesolvedit",
        }
        r = self.session.post(
            "https://api.partnerstack.com/v1/links",
            json=params, timeout=10
        )
        r.raise_for_status()
        data = r.json()
        return data.get("url", "")

    def to_offer(self, program: dict) -> Optional[AffiliateOffer]:
        """Convert raw PartnerStack data to normalized Offer."""
        try:
            attrs = program.get("attributes", program)
            name = attrs.get("name", attrs.get("program_name", ""))
            return AffiliateOffer(
                network="partnerstack",
                offer_id=str(program.get("id", attrs.get("id", ""))),
                program_name=name,
                advertiser=attrs.get("company", attrs.get("advertiser", "")),
                description=attrs.get("description", ""),
                category=self._map_category(
                    attrs.get("category", attrs.get("vertical", ""))
                ),
                commission_type=attrs.get("commission_type", "percentage"),
                commission_value=float(attrs.get("commission_value", attrs.get("rate", 0))),
                cookie_days=int(attrs.get("cookie_days", 30)),
                payout_model=attrs.get("payout_model", "sale"),
                geo_targets=attrs.get("geo_targets", ["US"]),
                price=float(attrs["price"]) if attrs.get("price") else None,
                raw_data=program,
            )
        except Exception as e:
            logger.warning(f"Failed to convert PartnerStack program: {e}")
            return None

    def _map_category(self, cat: str) -> str:
        mapping = {
            "saas": "wearables",
            "health": "biohacking",
            "fitness": "wearables",
            "wellness": "biohacking",
            "hardware": "red-light-therapy",
        }
        return mapping.get(cat.lower(), "biohacking")
