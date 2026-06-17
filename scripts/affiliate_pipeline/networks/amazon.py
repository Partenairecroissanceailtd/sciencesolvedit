"""
Amazon Associates Adapter
=========================
For promoting physical biohacking products via the Amazon Associates program.

Two modes:
  1. API mode (requires PAAPIv5 access key + secret + tag)
  2. Manual mode — user browses Amazon, pastes product URLs, I generate articles

Amazon link format:
  https://www.amazon.com/dp/ASIN?tag=YOUR_TAG-20
"""

from __future__ import annotations
import re, logging
from typing import Optional
from urllib.parse import urlencode, urlparse, parse_qs
from config import AffiliateOffer, logger


AMAZON_TAG = "sciencesolved-20"  # User's Amazon Associates tracking tag


class AmazonAdapter:
    """Amazon Associates adapter for product discovery and link generation."""

    def __init__(self, tag: str = ""):
        self.tag = tag.strip() if tag else AMAZON_TAG

    # ─── ASIN extraction ───

    ASIN_PATTERN = re.compile(r"/(?:dp|product|gp/product)/([A-Z0-9]{10})")
    URL_ASIN = re.compile(r"[A-Z0-9]{10}")

    @classmethod
    def extract_asin(cls, url_or_asin: str) -> Optional[str]:
        """Extract ASIN from an Amazon URL or return raw ASIN."""
        # Already an ASIN (10 alphanumeric chars)
        clean = url_or_asin.strip()
        if cls.ASIN_PATTERN.search(clean):
            return cls.ASIN_PATTERN.search(clean).group(1)
        if cls.URL_ASIN.fullmatch(clean):
            return clean
        return None

    def build_affiliate_link(self, asin: str) -> str:
        """Build an Amazon affiliate link with the user's tag."""
        if not self.tag:
            return f"https://www.amazon.com/dp/{asin}"
        params = urlencode({"tag": self.tag})
        return f"https://www.amazon.com/dp/{asin}?{params}"

    # ─── CSV import helpers ───

    def offer_from_csv_row(self, row: dict) -> Optional[AffiliateOffer]:
        """Convert a CSV row (from manual Amazon browsing) to an AffiliateOffer."""
        url_or_asin = row.get("product_url", row.get("asin", "")).strip()
        asin = self.extract_asin(url_or_asin)
        if not asin:
            logger.warning(f"Cannot parse ASIN from: {url_or_asin}")
            return None

        affiliate_link = self.build_affiliate_link(asin)
        name = row.get("program_name", row.get("product_name", f"Amazon Product {asin}"))
        price = None
        try:
            price = float(row.get("price", "0").replace("$", "")) or None
        except (ValueError, TypeError):
            pass

        return AffiliateOffer(
            network="amazon",
            offer_id=asin,
            program_name=name,
            advertiser=row.get("brand", "Amazon"),
            description=row.get("description", name),
            category=row.get("category", "biohacking"),
            commission_type="percentage",
            commission_value=row.get("commission", 4),  # Amazon avg 1-10%
            cookie_days=1,  # Amazon is 24h cookie (annoying but reality)
            price=price,
            tracking_link=affiliate_link,
            geo_targets=["US", "CA", "UK", "AU", "DE", "FR", "IT", "ES", "JP"],
        )

    def batch_from_csv(self, rows: list[dict]) -> list[AffiliateOffer]:
        """Convert multiple CSV rows to offers."""
        offers = []
        for row in rows:
            offer = self.offer_from_csv_row(row)
            if offer:
                offers.append(offer)
        return offers

    # ─── Template ───

    @staticmethod
    def csv_template_headers() -> list[str]:
        return [
            "product_url",
            "asin",
            "program_name",
            "brand",
            "description",
            "category",
            "price",
            "commission",
        ]

    @staticmethod
    def csv_template_rows() -> list[list[str]]:
        return [
            ["https://www.amazon.com/dp/B0CJ7Z8Y1P", "", "Joovv Mini 2.0", "Joovv", "Red light therapy device for targeted treatment", "red-light-therapy", "799", "4"],
            ["https://www.amazon.com/dp/B0BXP6ZP1Y", "", "Therabody Theragun Pro 6th Gen", "Therabody", "Percussive therapy device for muscle recovery", "wellness", "599", "4"],
            ["https://www.amazon.com/dp/B0CLR3MKDN", "", "Oura Ring Gen 4", "Oura", "Smart ring for sleep and activity tracking", "wearables", "349", "6"],
            ["https://www.amazon.com/dp/B0C4VK9SYZ", "", "Hyperice Normatec 3 Legs", "Hyperice", "Compression recovery boots for athletes", "wellness", "899", "3"],
            ["", "B0BX1P9C2K", "HigherDOSE Full Spectrum Sauna", "HigherDOSE", "Portable infrared sauna blanket", "sauna", "599", "4"],
        ]
