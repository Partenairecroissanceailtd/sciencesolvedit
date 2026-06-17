"""
Impact.com affiliate network adapter.
API docs: https://developer.impact.com/
"""

from __future__ import annotations
import logging, hashlib, time
from typing import Optional
import requests

from .config import AffiliateOffer, NetworkCredentials, logger

API_BASE = "https://api.impact.com"


class ImpactAdapter:
    """Fetch partnership catalogs from Impact.com API."""

    def __init__(self, credentials: NetworkCredentials):
        self.account_sid = credentials.api_key  # Account SID
        self.auth_token = credentials.api_secret  # Auth Token
        self.program_id = credentials.publisher_id  # Program/Campaign ID
        self.session = requests.Session()
        self.session.auth = (self.account_sid, self.auth_token)
        self.session.headers.update({"Accept": "application/json"})

    def test_auth(self) -> bool:
        """Verify credentials."""
        try:
            r = self.session.get(
                f"{API_BASE}/Accounts/{self.account_sid}/Campaigns",
                params={"PageSize": 1}, timeout=10
            )
            return r.status_code in (200, 204)
        except Exception as e:
            logger.error(f"Impact auth test failed: {e}")
            return False

    def fetch_campaigns(self, params: dict = None) -> list[dict]:
        """List available advertiser campaigns."""
        if params is None:
            params = {"PageSize": 100, "Sort": "Name"}
        r = self.session.get(
            f"{API_BASE}/Accounts/{self.account_sid}/Campaigns",
            params=params, timeout=30
        )
        r.raise_for_status()
        data = r.json()
        return data.get("Campaigns", [])

    def fetch_catalog(self, campaign_id: str) -> list[dict]:
        """Fetch product catalog for a specific campaign/advertiser."""
        r = self.session.get(
            f"{API_BASE}/Accounts/{self.account_sid}"
            f"/Campaigns/{campaign_id}/Catalogs",
            params={"PageSize": 200}, timeout=30
        )
        r.raise_for_status()
        data = r.json()
        return data.get("Products", [])

    def fetch_creatives(self, campaign_id: str) -> list[dict]:
        """Fetch available creatives/banners for a campaign."""
        r = self.session.get(
            f"{API_BASE}/Accounts/{self.account_sid}"
            f"/Campaigns/{campaign_id}/Creatives",
            params={"PageSize": 50}, timeout=30
        )
        r.raise_for_status()
        return r.json()

    def generate_tracking_link(
        self, campaign_id: str, destination_url: str,
        sub_id: str = "", click_id: str = ""
    ) -> str:
        """Generate an Impact tracking URL for a campaign/product."""
        params = {
            "CampaignId": campaign_id,
            "DestinationUrl": destination_url,
            "SubId1": sub_id or "sciencesolvedit",
        }
        if click_id:
            params["ClickId"] = click_id
        r = self.session.post(
            f"{API_BASE}/Accounts/{self.account_sid}/TrackingLinks",
            json=params, timeout=10
        )
        r.raise_for_status()
        data = r.json()
        return data.get("TrackingUrl", "")

    def to_offer(self, campaign: dict) -> Optional[AffiliateOffer]:
        """Convert Impact campaign to normalized Offer."""
        try:
            return AffiliateOffer(
                network="impact",
                offer_id=str(campaign.get("Id", "")),
                program_name=campaign.get("Name", ""),
                advertiser=campaign.get("AdvertiserName", ""),
                description=campaign.get("Description", ""),
                category=self._map_category(
                    campaign.get("Category", campaign.get("Vertical", ""))
                ),
                commission_type=campaign.get("CommissionType", "percentage"),
                commission_value=float(
                    campaign.get("CommissionPercent", 
                        campaign.get("FixedCommission", 0))
                ),
                cookie_days=int(campaign.get("CookieDays", 30)),
                payout_model=campaign.get("PricingModel", "sale"),
                geo_targets=campaign.get("TargetCountries", ["US"]),
                merchant_logo=campaign.get("LogoUrl", ""),
                merchant_rating=float(campaign.get("Rating", 0)),
                raw_data=campaign,
            )
        except Exception as e:
            logger.warning(f"Failed to convert Impact campaign: {e}")
            return None

    def _map_category(self, cat: str) -> str:
        mapping = {
            "health-wellness": "biohacking",
            "electronics": "wearables",
            "sports-fitness": "cold-plunge",
            "home-living": "sauna",
            "medical-devices": "red-light-therapy",
        }
        return mapping.get(cat.lower(), "biohacking")
