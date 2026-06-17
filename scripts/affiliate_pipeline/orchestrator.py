#!/usr/bin/env python3
"""
Affiliate Pipeline Orchestrator
================================
Single entry point for the Science Solved It affiliate pipeline.

Usage:
  # Fetch PartnerStack programs, filter, score, export CSV for manual links
  python3 orchestrator.py --fetch --api-key YOUR_KEY

  # Import a manually filled CSV and generate review articles
  python3 orchestrator.py --import filled_offers.csv

  # Generate a blank CSV template
  python3 orchestrator.py --new-offer

Formulas applied:
  1. Niche filter: only biohacking categories (rlt, cold-plunge, pemf, etc.)
  2. Commission filter: ≥ $5 or ≥ 5% equivalent
  3. Cookie filter: ≥ 7 days
  4. Geo filter: US/CA/UK/AU only
  5. KYC filter: exclude KYC-required programs
  6. Scoring: 50 base + commission + cookie + price + geo + rating (cap 100)
  7. Threshold: score ≥ 80 passes to CSV
"""

from __future__ import annotations
import sys, os, csv, json, logging
from pathlib import Path
from datetime import datetime, timezone
from dataclasses import asdict

# Set up path so all modules can find each other
SCRIPT_DIR = Path(__file__).parent.resolve()
sys.path.insert(0, str(SCRIPT_DIR))

from config import AffiliateOffer, load_config, logger
from engine import FilterEngine
from content_pipeline import ContentPipeline

# Network adapters
from networks.partnerstack import PartnerStackAdapter
from networks.amazon import AmazonAdapter
HAS_PS = True

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
)


def load_category_mapping() -> dict[str, str]:
    """Map PartnerStack categories to our internal niche taxonomy."""
    return {
        # Biohacking / wellness hardware
        "red light therapy": "red-light-therapy",
        "red-light-therapy": "red-light-therapy",
        "cold plunge": "cold-plunge",
        "cold-plunge": "cold-plunge",
        "pemf": "pemf",
        "pemf therapy": "pemf",
        "wearables": "wearables",
        "wearable tech": "wearables",
        "smart ring": "wearables",
        "fitness tracker": "wearables",
        "sauna": "sauna",
        "infrared sauna": "sauna",
        "biohacking": "biohacking",
        "supplements": "supplements",
        "nutrition": "supplements",
        "nootropics": "supplements",
        # Health monitoring
        "health tech": "health-monitoring",
        "medical devices": "health-monitoring",
        "health & fitness": "health-monitoring",
        "healthcare": "health-monitoring",
        "sleep tech": "health-monitoring",
        "sleep": "health-monitoring",
        # Home health
        "air purification": "home-health",
        "air purifier": "home-health",
        "water filtration": "home-health",
        "water filter": "home-health",
        # Ergonomics / workspace
        "ergonomics": "ergonomics",
        "office": "ergonomics",
        "standing desk": "ergonomics",
        # General wellness
        "health & wellness": "wellness",
        "wellness": "wellness",
        "fitness": "wellness",
        "recovery": "wellness",
        "massage": "wellness",
        "sports": "wellness",
        "beauty": "wellness",
        "skincare": "wellness",
        # Tech
        "technology": "tech",
        "electronics": "tech",
        "audio": "tech",
        # Home/ lifestyle
        "home": "home",
        "home & garden": "home",
    }


# Display labels for CSV output
NICHE_DISPLAY = {
    "red-light-therapy": "Red Light Therapy",
    "cold-plunge": "Cold Plunge / Ice Baths",
    "pemf": "PEMF Therapy",
    "wearables": "Wearables & Smart Rings",
    "sauna": "Sauna (Infrared / Portable)",
    "biohacking": "Biohacking",
    "supplements": "Supplements & Nootropics",
    "health-monitoring": "Health Monitoring (CGM, BP, Sleep)",
    "home-health": "Air & Water Quality",
    "ergonomics": "Ergonomics & Workspace",
    "wellness": "Wellness & Recovery",
    "tech": "Tech & Electronics",
    "home": "Home & Lifestyle",
}


def fetch_and_score(api_key: str) -> list[tuple[AffiliateOffer, float]]:
    """Fetch from PartnerStack API, categorize, filter, score, rank."""
    if not HAS_PS:
        logger.error("PartnerStack adapter not available")
        return []

    config = load_config()
    adapter = PartnerStackAdapter(api_key)
    programs = adapter.fetch_programs(limit=250)

    if not programs:
        logger.warning("No programs returned from PartnerStack API")
        return []

    category_map = load_category_mapping()
    offers = adapter.programs_to_offers(programs, category_map)

    logger.info(f"Raw programs: {len(programs)}, parsed offers: {len(offers)}")

    # Apply filter + scoring
    engine = FilterEngine(config)
    scored = engine.rank(offers)

    # Log by category
    by_cat: dict[str, list] = {}
    for offer, score in scored:
        c = offer.category
        if c not in by_cat:
            by_cat[c] = []
        by_cat[c].append((offer, score))

    logger.info(f"Scored offers by category:")
    for cat, items in sorted(by_cat.items()):
        display = NICHE_DISPLAY.get(cat, cat)
        logger.info(f"  {display}: {len(items)} offers (avg score: {sum(s for _, s in items)/len(items):.0f})")

    return scored


def export_csv(
    scored: list[tuple[AffiliateOffer, float]],
    output_path: str = None,
    threshold: float = 80.0,
) -> str:
    """
    Export scored offers to CSV for manual link insertion.
    Applies formulas: only score >= threshold.
    Columns designed for easy copy-paste from PartnerStack dashboard.
    """
    if output_path is None:
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        output_path = f"partnerstack_offers_{timestamp}.csv"

    offers_csv = Path(output_path)
    headers = [
        "network",
        "offer_id",
        "program_name",
        "advertiser",
        "category",
        "niche_display",
        "price",
        "commission_type",
        "commission_value",
        "cookie_days",
        "geo_targets",
        "score",
        "tracking_link",  # <-- USER FILLS THIS
        "description",
    ]

    # Filter by threshold
    qualified = [(o, s) for o, s in scored if s >= threshold]
    qualified.sort(key=lambda x: x[1], reverse=True)

    total_raw = len(scored)
    total_qualified = len(qualified)

    with open(offers_csv, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(headers)

        for offer, score in qualified:
            writer.writerow([
                offer.network,
                offer.offer_id,
                offer.program_name,
                offer.advertiser,
                offer.category,
                NICHE_DISPLAY.get(offer.category, offer.category),
                f"${offer.price:.2f}" if offer.price else "",
                offer.commission_type,
                f"{offer.commission_value}{'%' if offer.commission_type == 'percentage' else '$'}",
                offer.cookie_days,
                "|".join(offer.geo_targets),
                f"{score:.1f}",
                "",  # tracking_link — user fills this in!
                offer.description[:200],
            ])

    # Also log summary
    logger.info(f"--- Formula Results ---")
    logger.info(f"Total programs from API: {total_raw}")
    logger.info(f"Passed filter + scoring (threshold ≥ {threshold}): {total_qualified}")
    logger.info(f"Excluded (below threshold): {total_raw - total_qualified}")

    for offer, score in qualified:
        logger.info(f"  ✓ [{score:.0f}] {offer.program_name} ({NICHE_DISPLAY.get(offer.category, offer.category)})")

    for offer, score in sorted(scored, key=lambda x: x[1]):
        if score < threshold:
            reasons = []
            engine = FilterEngine(load_config())
            if not engine._filter_niche(offer):
                reasons.append("niche mismatch")
            if not engine._filter_min_commission(offer):
                reasons.append("low commission")
            if not engine._filter_cookie(offer):
                reasons.append("low cookie")
            if not engine._filter_geo(offer):
                reasons.append("geo mismatch")
            if not engine._filter_kyc(offer):
                reasons.append("KYC required")
            logger.info(f"  ✗ [{score:.0f}] {offer.program_name} — excluded ({', '.join(reasons) if reasons else 'below threshold'})")

    logger.info(f"\nCSV saved: {offers_csv.resolve()}")
    logger.info(f"Instructions: Fill 'tracking_link' column from PartnerStack dashboard → Offers → copy link")

    return str(offers_csv.resolve())


def generate_template(output_path: str = None):
    """Generate a blank CSV template for manual entry."""
    if output_path is None:
        output_path = "offers_template.csv"

    headers = [
        "network",
        "offer_id",
        "program_name",
        "advertiser",
        "description",
        "category",
        "price",
        "commission_type",
        "commission_value",
        "cookie_days",
        "tracking_link",
    ]

    example_rows = [
        ["partnerstack", "ex-1", "Joovv Mini 2.0", "Joovv", "Red light therapy device for targeted treatment", "red-light-therapy", "$799", "percentage", "10", "90", ""],
        ["partnerstack", "ex-2", "Theragun Pro", "Therabody", "Professional percussive therapy device", "wearables", "$599", "percentage", "8", "30", ""],
        ["partnerstack", "ex-3", "Oura Ring Gen 4", "Oura", "Smart ring for sleep and activity tracking", "wearables", "$349", "fixed", "20", "30", ""],
    ]

    with open(output_path, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(headers)
        for row in example_rows:
            writer.writerow(row)

    logger.info(f"Template saved: {output_path}")
    logger.info("Edit the CSV, fill in tracking links, then run with --import")
    return str(Path(output_path).resolve())


def import_csv(csv_path: str, dry_run: bool = True):
    """Import a CSV with filled tracking links and generate articles."""
    path = Path(csv_path)
    if not path.exists():
        logger.error(f"CSV not found: {path}")
        return []

    offers = []
    with open(path, newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            # Auto-generate Amazon affiliate links from product_url or ASIN
            tracking_link = row.get("tracking_link", "").strip()
            if not tracking_link and (row.get("product_url") or row.get("asin")):
                try:
                    from networks.amazon import AmazonAdapter
                    tag = row.get("amazon_tag", row.get("tracking_tag", ""))
                    ada = AmazonAdapter(tag)
                    asin = ada.extract_asin(row.get("product_url", "") or row.get("asin", ""))
                    if asin:
                        tracking_link = ada.build_affiliate_link(asin)
                        row["network"] = "amazon"
                        row["offer_id"] = asin
                except Exception:
                    pass

            # Skip rows without tracking links
            if not tracking_link:
                logger.info(f"Skipping {row.get('program_name', '?')} — no tracking_link or product_url/asin")
                continue

            price = None
            raw_price = row.get("price", "").replace("$", "").strip()
            if raw_price:
                try:
                    price = float(raw_price)
                except ValueError:
                    pass

            commission_value = 0.0
            raw_comm = row.get("commission_value", "0").replace("$", "").replace("%", "").strip()
            try:
                commission_value = float(raw_comm)
            except ValueError:
                pass

            offer = AffiliateOffer(
                network=row.get("network", "manual"),
                offer_id=row.get("offer_id", ""),
                program_name=row.get("program_name", ""),
                advertiser=row.get("advertiser", ""),
                description=row.get("description", ""),
                category=row.get("category", ""),
                price=price,
                commission_type=row.get("commission_type", "percentage"),
                commission_value=commission_value,
                cookie_days=int(row.get("cookie_days", "30") or 30),
                tracking_link=tracking_link,
            )
            offers.append(offer)

    logger.info(f"Loaded {len(offers)} offers from {csv_path}")

    if not offers:
        logger.warning("No offers with tracking links found.")
        return []

    if dry_run:
        logger.info("--- DRY RUN — would generate articles for: ---")
        for o in offers:
            logger.info(f"  ✓ {o.program_name} → {o.tracking_link}")
        return offers

    # Generate articles
    config = load_config()
    pipeline = ContentPipeline(config)

    for offer in offers:
        content = pipeline.generate_article(offer)
        path = pipeline.save_article(offer, content, dry_run=False)
        if path:
            logger.info(f"Article generated: {path}")

    return offers


def main():
    import argparse

    parser = argparse.ArgumentParser(
        description="Affiliate Pipeline — Science Solved It",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )

    parser.add_argument("--fetch", action="store_true", help="Fetch programs from PartnerStack API")
    parser.add_argument("--api-key", type=str, help="PartnerStack API key (or set PARTNERSTACK_API_KEY env var)")
    parser.add_argument("--threshold", type=float, default=80.0, help="Minimum score threshold (default: 80)")
    parser.add_argument("--output", type=str, help="Output CSV path")
    parser.add_argument("--import", dest="import_csv", type=str, help="Import a CSV with tracking links")
    parser.add_argument("--new-offer", action="store_true", help="Generate a blank CSV template")
    parser.add_argument("--amazon-template", action="store_true", help="Generate an Amazon Associates CSV template with example products")
    parser.add_argument("--amazon-tag", type=str, default="sciencesolved-20", help="Amazon Associates tracking tag (default: sciencesolved-20)")
    parser.add_argument("--dry-run", action="store_true", help="Preview without writing files")

    args = parser.parse_args()

    if args.new_offer:
        path = generate_template(args.output)
        print(f"\n✅ Template generated: {path}")
        print("   1. Fill in program names, descriptions, and tracking links")
        print("   2. Run: python3 orchestrator.py --import filled.csv")
        return

    if args.amazon_template:
        from networks.amazon import AmazonAdapter
        import csv
        tag = args.amazon_tag or "YOUR-TAG-20"
        output = args.output or "amazon_products_template.csv"
        headers = AmazonAdapter.csv_template_headers() + ["amazon_tag"]
        rows = AmazonAdapter.csv_template_rows()
        with open(output, "w", newline="") as f:
            w = csv.writer(f)
            w.writerow(headers)
            for row in rows:
                w.writerow(row + [tag])
        print(f"\n✅ Amazon template generated: {output}")
        print(f"   Your tag: {tag}")
        print("   1. Browse amazon.com for biohacking products")
        print("   2. Copy product URLs into the CSV")
        print("   3. Fill in product names, descriptions, categories")
        print(f"   4. Run: python3 orchestrator.py --import {output}")
        print(f"      (Your tag '{tag}' is already in the CSV)")
        return

    if args.import_csv:
        import_csv(args.import_csv, dry_run=args.dry_run)
        return

    if args.fetch:
        api_key = args.api_key or os.environ.get("PARTNERSTACK_API_KEY", "")
        if not api_key:
            print("❌ API key required. Use --api-key KEY or set PARTNERSTACK_API_KEY env var.")
            sys.exit(1)

        scored = fetch_and_score(api_key)
        if not scored:
            print("❌ No programs fetched or all filtered out.")
            sys.exit(1)

        path = export_csv(scored, output_path=args.output, threshold=args.threshold)
        print(f"\n✅ CSV generated: {path}")
        print(f"   Offers fetched: {len(scored)}")
        print(f"   Qualified (score ≥ {args.threshold}): {sum(1 for _, s in scored if s >= args.threshold)}")
        print(f"\n📋 NEXT STEP: Open the CSV, paste tracking links from PartnerStack dashboard,")
        print(f"   then run: python3 orchestrator.py --import {path}")
        return

    parser.print_help()


if __name__ == "__main__":
    main()
