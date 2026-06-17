"""
Offer filter engine.
Applies configurable filters across all network offers.
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Callable
from config import AffiliateOffer, load_config, logger


class FilterEngine:
    """Multi-stage offer filter pipeline."""

    def __init__(self, config: dict = None):
        self.config = config or load_config()
        filters_cfg = self.config.get("filters", {})
        self.min_commission = filters_cfg.get("min_commission", 5)
        self.min_cookie = filters_cfg.get("min_cookie_days", 7)
        self.target_geo = set(filters_cfg.get("target_geo", ["US"]))
        self.target_niches = set(filters_cfg.get("target_niches", []))
        self.exclude_kyc = filters_cfg.get("exclude_kyc", True)

    def filter(self, offers: list[AffiliateOffer]) -> list[AffiliateOffer]:
        """Run all filters in sequence."""
        pipeline = [
            ("niche", self._filter_niche),
            ("commission", self._filter_min_commission),
            ("cookie", self._filter_cookie),
            ("geo", self._filter_geo),
            ("kyc", self._filter_kyc),
        ]
        results = offers[:]
        for name, fn in pipeline:
            before = len(results)
            results = [o for o in results if fn(o)]
            after = len(results)
            removed = before - after
            if removed:
                logger.info(f"Filter [{name}]: removed {removed} offers ({after} remaining)")
        return results

    def score_offer(self, offer: AffiliateOffer) -> float:
        """Score an offer on quality/fit (higher = better).
        
        Heavily weighted toward mid-to-high ticket biohacking products.
        """
        score = 50.0  # baseline

        # Commission bonus
        if offer.commission_type == "percentage":
            score += min(offer.commission_value * 2, 30)  # up to +30
        elif offer.commission_type == "fixed":
            score += min(offer.commission_value / 10, 20)

        # Cookie length bonus
        if offer.cookie_days >= 90:
            score += 10
        elif offer.cookie_days >= 30:
            score += 5
        elif offer.cookie_days >= 14:
            score += 2

        # 💰 HIGH-TICKET FOCUS — heavy price weighting
        # Premium biohacking hardware is the sweet spot
        if offer.price and offer.price > 1000:
            score += 30   # Saunas, full-body RL panels, high-end PEMF
        elif offer.price and offer.price > 500:
            score += 20   # Mid-range RL panels, Therabody, cryo chambers
        elif offer.price and offer.price > 200:
            score += 10   # Oura Ring, entry-level RL devices
        elif offer.price and offer.price > 100:
            score += 5    # Supplements, basic wearables

        # Geo relevance
        us_match = 1.0 if "US" in offer.geo_targets else 0.0
        score += us_match * 5

        # Merchant rating
        if offer.merchant_rating > 4.0:
            score += 5
        elif offer.merchant_rating > 3.0:
            score += 2

        # 🧪 FUTURE: Demand signal bonus (Apify keyword volume data)
        # score += demand_bonus  -- added when Apify pipeline is connected

        return round(min(score, 100), 1)

    def rank(self, offers: list[AffiliateOffer]) -> list[tuple[AffiliateOffer, float]]:
        """Filter then score-rank all offers."""
        filtered = self.filter(offers)
        scored = [(o, self.score_offer(o)) for o in filtered]
        scored.sort(key=lambda x: x[1], reverse=True)
        return scored

    # --- Individual filter functions ---

    def _filter_niche(self, o: AffiliateOffer) -> bool:
        if not self.target_niches:
            return True
        # Exact category match (fast path)
        if o.category.lower() in {n.lower() for n in self.target_niches}:
            return True
        # Fuzzy: check if program name or description matches domain keywords
        # This catches uncategorized but relevant products
        domain_keywords = self.config.get("domain", {}).get("relevance_keywords", [])
        text_to_check = f"{o.program_name} {o.description}".lower()
        for kw in domain_keywords:
            if kw.lower() in text_to_check:
                logger.debug(f"Niche fuzzy-match: '{kw}' in '{o.program_name}'")
                return True
        return False

    def _filter_min_commission(self, o: AffiliateOffer) -> bool:
        return o.commission_value >= self.min_commission

    def _filter_cookie(self, o: AffiliateOffer) -> bool:
        return o.cookie_days >= self.min_cookie

    def _filter_geo(self, o: AffiliateOffer) -> bool:
        return bool(set(g.upper() for g in o.geo_targets) & self.target_geo)

    def _filter_kyc(self, o: AffiliateOffer) -> bool:
        if not self.exclude_kyc:
            return True
        return not o.kyc_required
