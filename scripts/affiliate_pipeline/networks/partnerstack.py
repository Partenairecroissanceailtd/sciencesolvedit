"""
PartnerStack — Marketplace Program Fetcher
===========================================
Uses the PartnerStack Partner API (v2) to list all active marketplace programs.
The read API key works as a Bearer token.

Endpoint: GET https://api.partnerstack.com/api/v2/marketplace/programs
Docs: https://docs.partnerstack.com/reference/get_v2-marketplace-programs
"""

from __future__ import annotations
import json, logging
from typing import Optional
from urllib.request import Request, urlopen
from urllib.error import HTTPError
from config import AffiliateOffer, logger

API_BASE = "https://api.partnerstack.com/api/v2"
MAX_PROGRAMS = 250  # API limit cap


class PartnerStackAdapter:
    """Fetch marketplace programs from PartnerStack API."""

    def __init__(self, api_key: str):
        self.api_key = api_key.strip() if api_key else ""
        self._headers = {
            "Accept": "application/json",
            "Authorization": f"Bearer {self.api_key}",
        }

    def fetch_programs(self, limit: int = MAX_PROGRAMS) -> list[dict]:
        """Fetch all active marketplace-listed programs."""
        if not self.api_key:
            logger.warning("PartnerStack API key not set — cannot fetch programs.")
            return []

        url = f"{API_BASE}/marketplace/programs?limit={limit}"
        logger.info(f"Fetching PartnerStack programs from: {url}")

        try:
            req = Request(url, headers=self._headers, method="GET")
            with urlopen(req, timeout=30) as resp:
                data = json.loads(resp.read().decode())
        except HTTPError as e:
            body = e.read().decode() if e.fp else ""
            logger.error(f"PartnerStack API error {e.code}: {body[:500]}")
            return []
        except Exception as e:
            logger.error(f"PartnerStack request failed: {e}")
            return []

        # The API returns a list of program objects
        if isinstance(data, dict):
            programs = data.get("data", data.get("results", []))
            if not programs:
                programs = [data]
        elif isinstance(data, list):
            programs = data
        else:
            logger.warning(f"Unexpected response format: {type(data)}")
            return []

        logger.info(f"Fetched {len(programs)} programs from PartnerStack")
        return programs

    def programs_to_offers(
        self, programs: list[dict], category_mapping: dict[str, str] = None
    ) -> list[AffiliateOffer]:
        """Convert raw PartnerStack programs into normalized AffiliateOffer list."""
        if category_mapping is None:
            category_mapping = {}  # fallback: use raw category

        offers = []
        for prog in programs:
            if not isinstance(prog, dict):
                continue

            program_name = prog.get("name") or prog.get("title") or "Unknown"
            advertiser = prog.get("advertiser_name") or prog.get("company") or "Unknown"
            description = (
                prog.get("description")
                or prog.get("teaser")
                or f"{program_name} by {advertiser}"
            )
            raw_cat = (prog.get("category") or prog.get("vertical") or "").lower()
            category = category_mapping.get(raw_cat, raw_cat)

            # Pricing
            price = None
            try:
                price = float(prog.get("price") or 0) or None
            except (ValueError, TypeError):
                pass

            # Commission
            commission_type = "percentage"
            commission_value = 0.0
            raw_comm = prog.get("commission") or prog.get("recurrence_rate") or {}
            if isinstance(raw_comm, dict):
                commission_type = raw_comm.get("type", "percentage")
                try:
                    commission_value = float(raw_comm.get("value", 0))
                except (ValueError, TypeError):
                    pass
            elif isinstance(raw_comm, (int, float)):
                commission_value = float(raw_comm)

            # Cookie days
            cookie_days = 30
            try:
                cookie_days = int(prog.get("cookie_days") or 30)
            except (ValueError, TypeError):
                pass

            # Geo targets
            geo = prog.get("geo_targets", prog.get("countries", []))
            if isinstance(geo, str):
                geo = [geo]
            if not geo:
                geo = ["US", "CA", "UK", "AU"]

            # KYC
            kyc = bool(prog.get("kyc_required", prog.get("approval_required", False)))

            offer = AffiliateOffer(
                network="partnerstack",
                offer_id=prog.get("id") or prog.get("key") or program_name.lower().replace(" ", "-"),
                program_name=program_name,
                advertiser=advertiser,
                description=description,
                category=category,
                commission_type=commission_type,
                commission_value=commission_value,
                cookie_days=cookie_days,
                price=price,
                geo_targets=geo if isinstance(geo, list) else [geo],
                kyc_required=kyc,
                tracking_link="",  # User fills this in from their dashboard
                tags=prog.get("tags", []),
                raw_data=prog,
            )
            offers.append(offer)

        return offers
