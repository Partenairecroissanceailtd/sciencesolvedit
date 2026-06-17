"""
Automatic affiliate link generator.
Creates tracking links and deeplinks via each network's API.
"""

from __future__ import annotations
import logging
from typing import Optional
from .config import AffiliateOffer, load_config, logger
from .networks.awin import AwinAdapter
from .networks.partnerstack import PartnerStackAdapter
from .networks.impact import ImpactAdapter


class LinkGenerator:
    """Generate tracking links for offers across all networks."""

    def __init__(self, config: dict = None):
        self.config = config or load_config()
        self._adapters = {}

    def _get_adapter(self, network: str):
        """Lazy-load the network adapter."""
        if network not in self._adapters:
            creds = self.config.get(network, {})
            if network == "awin":
                nc = type("obj", (object,), {"api_key": creds.get("api_key", ""), "publisher_id": creds.get("publisher_id", "")})()
                self._adapters[network] = AwinAdapter(nc)
            elif network == "partnerstack":
                nc = type("obj", (object,), {"api_key": creds.get("api_key", ""), "api_secret": creds.get("api_secret", "")})()
                self._adapters[network] = PartnerStackAdapter(nc)
            elif network == "impact":
                nc = type("obj", (object,), {"api_key": creds.get("account_sid", ""), "api_secret": creds.get("auth_token", ""), "publisher_id": creds.get("program_id", "")})()
                self._adapters[network] = ImpactAdapter(nc)
        return self._adapters.get(network)

    def generate(self, offer: AffiliateOffer, destination_url: str = "") -> str:
        """Generate a tracking/deeplink for the given offer."""
        if not destination_url:
            destination_url = f"https://www.sciencesolvedit.store/go/{offer.network}/{offer.offer_id}/"

        adapter = self._get_adapter(offer.network)
        if not adapter:
            logger.warning(f"No adapter for network: {offer.network}")
            return destination_url

        try:
            if offer.network == "awin":
                link = adapter.generate_deeplink(int(offer.offer_id), destination_url)
            elif offer.network == "partnerstack":
                link = adapter.generate_tracking_link(offer.offer_id, destination_url)
            elif offer.network == "impact":
                link = adapter.generate_tracking_link(offer.offer_id, destination_url)
            else:
                link = destination_url

            if link:
                offer.tracking_link = link
                return link
        except Exception as e:
            logger.error(f"Link generation failed for {offer.network}/{offer.offer_id}: {e}")

        offer.tracking_link = destination_url
        return destination_url

    def batch_generate(self, offers: list[AffiliateOffer]) -> list[AffiliateOffer]:
        """Generate tracking links for all offers."""
        for offer in offers:
            self.generate(offer)
        return offers
