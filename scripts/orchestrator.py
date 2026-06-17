#!/usr/bin/env python3
"""
Affiliate Pipeline Orchestrator
================================
Single entry point for the full workflow.

Usage:
  # Auto-pull from networks (when you have API keys)
  python orchestrator.py --network awin --limit 5
  python orchestrator.py --all-networks --filter-only

  # Manual import (for PartnerStack or any manual links)
  python orchestrator.py --import offers.csv
  python orchestrator.py --import offers.json --dry-run

  # Generate a blank CSV template
  python orchestrator.py --new-offer

  # Config
  python orchestrator.py --show-config
  python orchestrator.py --init-config
"""

from __future__ import annotations
import argparse, json, sys, csv, logging
from pathlib import Path
from datetime import datetime, timezone

sys.path.insert(0, str(Path(__file__).parent))
from affiliate_pipeline.config import load_config, save_config, AffiliateOffer, logger
from affiliate_pipeline.engine import FilterEngine
from affiliate_pipeline.link_generator import LinkGenerator
from affiliate_pipeline.content_pipeline import ContentPipeline
from affiliate_pipeline.networks.awin import AwinAdapter
from affiliate_pipeline.networks.partnerstack import PartnerStackAdapter
from affiliate_pipeline.networks.impact import ImpactAdapter

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)


# ---------------------------------------------------------------------------
# Manual import: read offers from CSV or JSON
# ---------------------------------------------------------------------------

def read_offers_from_csv(path: str) -> list[AffiliateOffer]:
    """Read offers from a CSV file with required columns."""
    offers = []
    with open(path, newline="") as f:
        reader = csv.DictReader(f)
        for i, row in enumerate(reader, 1):
            try:
                offer = AffiliateOffer(
                    network=row.get("network", "manual"),
                    offer_id=row.get("offer_id", str(i)),
                    program_name=row.get("program_name", row.get("product", "")),
                    advertiser=row.get("advertiser", row.get("brand", "")),
                    description=row.get("description", ""),
                    category=row.get("category", "biohacking"),
                    commission_type=row.get("commission_type", "percentage"),
                    commission_value=float(row.get("commission_value", 0) or 0),
                    cookie_days=int(row.get("cookie_days", 30) or 30),
                    price=float(row["price"]) if row.get("price") else None,
                    tracking_link=row.get("tracking_link", row.get("affiliate_url", "")),
                    deeplink=row.get("deeplink", ""),
                    merchant_logo=row.get("logo", ""),
                )
                offers.append(offer)
            except Exception as e:
                logger.warning(f"Row {i} skipped — {e}")
    return offers


def read_offers_from_json(path: str) -> list[AffiliateOffer]:
    """Read offers from a JSON file (array of objects)."""
    with open(path) as f:
        data = json.load(f)
    offers = []
    for i, item in enumerate(data, 1):
        try:
            offer = AffiliateOffer(
                network=item.get("network", "manual"),
                offer_id=item.get("offer_id", str(i)),
                program_name=item.get("program_name", item.get("product", "")),
                advertiser=item.get("advertiser", item.get("brand", "")),
                description=item.get("description", ""),
                category=item.get("category", "biohacking"),
                commission_type=item.get("commission_type", "percentage"),
                commission_value=float(item.get("commission_value", 0) or 0),
                cookie_days=int(item.get("cookie_days", 30) or 30),
                price=float(item["price"]) if item.get("price") else None,
                tracking_link=item.get("tracking_link", item.get("affiliate_url", "")),
                deeplink=item.get("deeplink", ""),
                merchant_logo=item.get("logo", ""),
                raw_data=item,
            )
            offers.append(offer)
        except Exception as e:
            logger.warning(f"Item {i} skipped — {e}")
    return offers


def write_csv_template(path: str):
    """Generate a blank CSV template for manual offer entry."""
    rows = [
        {
            "network": "manual",
            "offer_id": "1",
            "program_name": "Example Product Pro X",
            "advertiser": "ExampleBrand",
            "description": "A short description of the product for the review meta.",
            "category": "red-light-therapy",
            "price": "499",
            "commission_type": "percentage",
            "commission_value": "10",
            "cookie_days": "30",
            "tracking_link": "https://example.com/?ref=yourlink",
            "deeplink": "",
            "logo": "",
        },
        {
            "network": "manual",
            "offer_id": "2",
            "program_name": "",
            "advertiser": "",
            "description": "",
            "category": "cold-plunge",
            "price": "",
            "commission_type": "fixed",
            "commission_value": "25",
            "cookie_days": "90",
            "tracking_link": "",
            "deeplink": "",
            "logo": "",
        },
    ]
    with open(path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=rows[0].keys())
        writer.writeheader()
        writer.writerows(rows)
    print(f"CSV template created: {path}")
    print("Fill it with your PartnerStack offers and run:")
    print(f"  python orchestrator.py --import {path}")


# ---------------------------------------------------------------------------
# Network adapter helper
# ---------------------------------------------------------------------------

def get_adapter(network: str, config: dict):
    creds = config.get(network, {})
    if network == "awin":
        nc = type("obj", (object,), {
            "api_key": creds.get("api_key", ""),
            "api_secret": creds.get("api_secret", ""),
            "publisher_id": creds.get("publisher_id", ""),
        })()
        return AwinAdapter(nc)
    elif network == "partnerstack":
        nc = type("obj", (object,), {
            "api_key": creds.get("api_key", ""),
            "api_secret": creds.get("api_secret", ""),
            "publisher_id": "",
        })()
        return PartnerStackAdapter(nc)
    elif network == "impact":
        nc = type("obj", (object,), {
            "api_key": creds.get("account_sid", ""),
            "api_secret": creds.get("auth_token", ""),
            "publisher_id": creds.get("program_id", ""),
        })()
        return ImpactAdapter(nc)
    return None


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Affiliate Pipeline Orchestrator")
    parser.add_argument("--network", choices=["awin", "partnerstack", "impact"], help="Which network to pull from")
    parser.add_argument("--all-networks", action="store_true", help="Pull from all configured networks")
    parser.add_argument("--import", dest="import_file", type=str, help="Import offers from CSV or JSON file (manual mode)")
    parser.add_argument("--new-offer", type=str, nargs="?", const="offers_template.csv", help="Generate a blank CSV template for manual offer entry")
    parser.add_argument("--limit", type=int, default=10, help="Max offers to process")
    parser.add_argument("--dry-run", action="store_true", help="Show what would happen without writing files")
    parser.add_argument("--filter-only", action="store_true", help="Fetch and filter only (no article generation)")
    parser.add_argument("--show-config", action="store_true", help="Print current config and exit")
    parser.add_argument("--init-config", action="store_true", help="Create config.json from template")
    args = parser.parse_args()

    # --- Special commands ---
    if args.show_config:
        config = load_config()
        for net in ["awin", "partnerstack", "impact"]:
            if net in config:
                for k, v in config[net].items():
                    if v and len(str(v)) > 4:
                        config[net][k] = v[:4] + "***"
        print(json.dumps(config, indent=2))
        return

    if args.new_offer:
        write_csv_template(args.new_offer)
        return

    if args.init_config:
        tmpl = Path(__file__).parent / "affiliate_pipeline" / "config.template.json"
        dst = Path(__file__).parent / "affiliate_pipeline" / "config.json"
        if dst.exists():
            print(f"Config already exists: {dst}")
            return
        dst.write_text(tmpl.read_text())
        print(f"Config template created: {dst}")
        print("Edit it with your API credentials, then run the pipeline.")
        return

    # --- Load pipeline ---
    config = load_config()
    engine = FilterEngine(config)
    content_pipe = ContentPipeline(config)
    all_offers: list[AffiliateOffer] = []

    # --- Manual import mode ---
    if args.import_file:
        path = args.import_file
        if path.endswith(".csv"):
            all_offers = read_offers_from_csv(path)
        elif path.endswith(".json"):
            all_offers = read_offers_from_json(path)
        else:
            print(f"Unsupported format: {path} (use .csv or .json)")
            return
        print(f"\n{'='*60}")
        print(f"  Imported {len(all_offers)} offers from {path}")
        print(f"{'='*60}")

    # --- Network fetch mode ---
    else:
        networks = []
        if args.all_networks:
            networks = ["awin", "partnerstack", "impact"]
        elif args.network:
            networks = [args.network]
        else:
            print("Specify --network, --all-networks, or --import <file>")
            parser.print_help()
            return

        for net_name in networks:
            print(f"\n{'='*60}")
            print(f"  Network: {net_name}")
            print(f"{'='*60}")
            adapter = get_adapter(net_name, config)
            if not adapter:
                print(f"  ⚠ No adapter for {net_name}")
                continue
            print(f"  Testing auth...")
            if not adapter.test_auth():
                print(f"  ❌ Auth failed — check your {net_name} credentials")
                continue
            print(f"  ✅ Auth OK")
            print(f"  Fetching offers...")
            try:
                if net_name == "awin":
                    raw = adapter.fetch_programs()
                elif net_name == "partnerstack":
                    raw = adapter.fetch_offers()
                elif net_name == "impact":
                    raw = adapter.fetch_campaigns()
                else:
                    raw = []
            except Exception as e:
                print(f"  ❌ Fetch failed: {e}")
                continue
            offers = []
            for item in raw[:args.limit]:
                offer = adapter.to_offer(item)
                if offer:
                    offers.append(offer)
            print(f"  Got {len(offers)} offers")
            all_offers.extend(offers)

    if not all_offers:
        print("\nNo offers. Nothing to process.")
        return

    # --- Filter & score ---
    print(f"\n{'='*60}")
    print(f"  Filtering {len(all_offers)} offers...")
    scored = engine.rank(all_offers)
    top = scored[:args.limit]
    print(f"  Top {len(top)} offers:")
    for i, (offer, score) in enumerate(top, 1):
        link = offer.tracking_link or offer.deeplink or ""
        link_short = link[:40] + "..." if len(link) > 40 else link
        print(f"  {i:2d}. [{score:5.1f}] {offer.program_name[:40]:40s} | {offer.category:20s} | {link_short}")

    if args.filter_only:
        out = [{"score": s, **o.to_dict()} for o, s in top]
        outfile = Path("filtered_offers.json")
        with open(outfile, "w") as f:
            json.dump(out, f, indent=2, default=str)
        print(f"\nFiltered offers exported to {outfile}")
        return

    # --- Generate articles ---
    print(f"\n{'='*60}")
    print(f"  Generating review articles...")
    for offer, score in top[:5]:
        print(f"  📝 {offer.program_name[:40]:40s}", end="")
        article = content_pipe.generate_article(offer)
        path = content_pipe.save_article(offer, article, dry_run=args.dry_run)
        if path:
            print(f" → {path}")
        else:
            print(f" [DRY RUN]")

    print(f"\n{'='*60}")
    print(f"  ✅ Done! {len(top)} offers processed.")
    if args.dry_run:
        print(f"  (Dry run — no files written)")
    print(f"{'='*60}")


if __name__ == "__main__":
    main()
