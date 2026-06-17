"""
Affiliate Network Pipeline — Science Solved It
================================================
Authenticate → Pull offers → Filter → Generate links → LLM draft → Publish

Supports: Awin, PartnerStack, Impact.com
"""

from __future__ import annotations
import os, json, time, logging
from dataclasses import dataclass, field, asdict
from typing import Optional
from pathlib import Path

logger = logging.getLogger("affiliate-pipeline")

# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------

@dataclass
class AffiliateOffer:
    """Normalized offer from any network."""
    network: str                    # "awin" | "partnerstack" | "impact" | "manual"
    offer_id: str
    program_name: str
    advertiser: str
    description: str
    category: str                   # mapped to our 5 niches
    subcategories: list[str] = field(default_factory=list)
    commission_type: str = ""       # "percentage" | "fixed" | "cpa" | "hybrid"
    commission_value: float = 0.0   # percentage or dollar amount
    cookie_days: int = 30
    payout_model: str = ""          # "sale" | "lead" | "click" | "install"
    currency: str = "USD"
    price: Optional[float] = None   # product price if available
    deeplink: str = ""
    tracking_link: str = ""
    geo_targets: list[str] = field(default_factory=lambda: ["US", "CA", "UK", "AU"])
    merchant_logo: str = ""
    merchant_rating: float = 0.0
    kyc_required: bool = False
    tags: list[str] = field(default_factory=list)
    raw_data: dict = field(default_factory=dict)

    def to_dict(self):
        return asdict(self)


@dataclass
class NetworkCredentials:
    api_key: str
    api_secret: str = ""
    publisher_id: str = ""
    endpoint: str = ""


# ---------------------------------------------------------------------------
# Config loader
# ---------------------------------------------------------------------------

CONFIG_PATH = Path(__file__).parent / "config.json"


def load_config() -> dict:
    """Load network credentials from config.json (user fills this in)."""
    if CONFIG_PATH.exists():
        with open(CONFIG_PATH) as f:
            return json.load(f)
    return {
        "awin": {"api_key": "", "publisher_id": ""},
        "partnerstack": {"api_key": "", "api_secret": ""},
        "impact": {"account_sid": "", "auth_token": "", "program_id": ""},
        "filters": {
            "min_commission": 5,
            "min_cookie_days": 7,
            "target_geo": ["US", "CA", "UK", "AU"],
            "target_niches": [
                "red-light-therapy", "cold-plunge", "pemf",
                "wearables", "sauna", "biohacking", "supplements"
            ],
            "exclude_kyc": True,
        },
        "publishing": {
            "output_dir": str(Path(__file__).parent.parent / "content" / "reviews"),
            "auto_publish": False,
        }
    }


def save_config(config: dict):
    with open(CONFIG_PATH, "w") as f:
        json.dump(config, f, indent=2)
    logger.info(f"Config saved to {CONFIG_PATH}")
