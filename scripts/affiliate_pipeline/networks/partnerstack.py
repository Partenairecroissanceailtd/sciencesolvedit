"""
PartnerStack — Manual Link Integration
=======================================
PartnerStack doesn't offer API keys for affiliate accounts.
Instead, you generate tracking links from their dashboard and
feed them into the pipeline via CSV import.

How to use:
  1. Go to PartnerStack dashboard → Offers
  2. Copy the affiliate/tracking link for each product
  3. Paste into a CSV (use `orchestrator.py --new-offer`)
  4. Run:  python orchestrator.py --import offers.csv

CSV columns:
  network, offer_id, program_name, advertiser, description,
  category, price, commission_type, commission_value,
  cookie_days, tracking_link, deeplink, logo
"""

from __future__ import annotations
from ..config import AffiliateOffer, logger

# This adapter exists for future use if PartnerStack ever
# allows API key access for affiliates. For now, use --import.
