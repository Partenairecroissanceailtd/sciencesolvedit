#!/usr/bin/env python3
"""
Affiliate Pipeline Orchestrator
================================
Single entry point for the full workflow:

  1. Load config (credentials + filters)
  2. Authenticate to each network
  3. Fetch offers/programs
  4. Filter & score
  5. Generate tracking links
  6. Generate review article (LLM draft)
  7. Save to content directory
  8. (Optional) Trigger publish

Usage:
  python orchestrator.py --network awin --limit 5
  python orchestrator.py --all-networks --filter-only
  python orchestrator.py --dry-run
"""

from __future__ import annotations
import argparse, json, sys, logging
from pathlib import Path

# Add parent to path so we can import
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


def get_adapter(network: str, config: dict):
    """Get the right network adapter based on config."""
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


def main():
    parser = argparse.ArgumentParser(description="Affiliate Pipeline Orchestrator")
    parser.add_argument("--network", choices=["awin", "partnerstack", "impact"], help="Which network to pull from")
    parser.add_argument("--all-networks", action="store_true", help="Pull from all configured networks")
    parser.add_argument("--limit", type=int, default=10, help="Max offers to process")
    parser.add_argument("--dry-run", action="store_true", help="Show what would happen without writing files")
    parser.add_argument("--filter-only", action="store_true", help="Fetch and filter only (no article generation)")
    parser.add_argument("--show-config", action="store_true", help="Print current config and exit")
    parser.add_argument("--init-config", action="store_true", help="Create config.json from template")
    args = parser.parse_args()

    # Handle special commands
    if args.show_config:
        config = load_config()
        # Mask secrets
        for net in ["awin", "partnerstack", "impact"]:
            if net in config:
                for k, v in config[net].items():
                    if v and len(str(v)) > 4:
                        config[net][k] = v[:4] + "***"
        print(json.dumps(config, indent=2))
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

    # Load config
    config = load_config()
    engine = FilterEngine(config)
    link_gen = LinkGenerator(config)
    content_pipe = ContentPipeline(config)

    # Determine which networks to pull
    networks = []
    if args.all_networks:
        networks = ["awin", "partnerstack", "impact"]
    elif args.network:
        networks = [args.network]
    else:
        print("Specify --network or --all-networks")
        parser.print_help()
        return

    all_offers: list[AffiliateOffer] = []

    for net_name in networks:
        print(f"\n{'='*60}")
        print(f"  Network: {net_name}")
        print(f"{'='*60}")

        adapter = get_adapter(net_name, config)
        if not adapter:
            print(f"  ⚠ No adapter for {net_name}")
            continue

        # Test auth
        print(f"  Testing auth...")
        if not adapter.test_auth():
            print(f"  ❌ Auth failed — check your {net_name} credentials in config.json")
            continue
        print(f"  ✅ Auth OK")

        # Fetch offers
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

        # Convert to normalized offers
        offers = []
        for item in raw[:args.limit]:
            offer = adapter.to_offer(item)
            if offer:
                offers.append(offer)

        print(f"  Got {len(offers)} offers")
        all_offers.extend(offers)

    if not all_offers:
        print("\nNo offers found. Nothing to process.")
        return

    # Filter & score
    print(f"\n{'='*60}")
    print(f"  Filtering {len(all_offers)} offers...")
    scored = engine.rank(all_offers)
    top = scored[:args.limit]

    print(f"  Top {len(top)} offers after filtering:")
    for i, (offer, score) in enumerate(top, 1):
        print(f"  {i:2d}. [{score:5.1f}] {offer.program_name[:50]:50s} | {offer.network:12s} | {offer.category}")

    if args.filter_only:
        # Export filtered offers as JSON
        out = [{"score": s, **o.to_dict()} for o, s in top]
        outfile = Path("filtered_offers.json")
        with open(outfile, "w") as f:
            json.dump(out, f, indent=2, default=str)
        print(f"\nFiltered offers exported to {outfile}")
        return

    # Generate tracking links
    print(f"\n{'='*60}")
    print(f"  Generating tracking links...")
    for offer, score in top[:5]:  # Limit to top 5 for article generation
        link = link_gen.generate(offer)
        print(f"  ✅ {offer.program_name[:40]:40s} → {link[:60]}...")

    # Generate articles
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
    print(f"  Done! {len(top)} offers processed.")
    if args.dry_run:
        print(f"  (Dry run — no files written)")
    print(f"{'='*60}")


if __name__ == "__main__":
    main()
