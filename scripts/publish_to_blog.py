#!/usr/bin/env python3
"""
Scoring Engine → Astro Content Pipeline

Takes scored products (from opportunity_scorer.py batch output),
generates MDX review files in the Astro blog content directory.

Usage:
  python3 publish_to_blog.py --products products.json --output ../src/content/reviews/
  python3 publish_to_blog.py --score-all   # Run scorer on all batch items first
"""

import json
import os
import sys
import argparse
import subprocess
import re
from datetime import datetime, timezone
from pathlib import Path

BLOG_CONTENT_DIR = Path("/opt/data/affiliate-blog/src/content")
SCORER_PATH = Path("/opt/data/scoring-engine/opportunity_scorer.py")
SCORER_BATCH = Path("/opt/data/scoring-engine/inputs/")
SCORER_OUTPUT = Path("/opt/data/scoring-engine/products/pass/")

CATEGORY_MAP = {
    "red-light-therapy": "red-light-therapy",
    "cold-plunge": "cold-plunge",
    "pemf": "pemf",
    "wearables": "wearables",
    "sauna": "sauna",
    "supplements": "supplements",
    "nootropic": "supplements",
    "fitness": "wearables",
    "sleep": "wearables",
}

def slugify(text):
    """Convert text to URL-safe slug."""
    text = text.lower().strip()
    text = re.sub(r'[^\w\s-]', '', text)
    text = re.sub(r'[-\s]+', '-', text)
    return text[:80]


def generate_review_mdx(product: dict):
    """Generate a review MDX file from scored product data."""
    name = product.get("name", "Product")
    slug = slugify(name)
    category = CATEGORY_MAP.get(product.get("_category", ""), "other")
    price = product.get("price", 0)
    score = product.get("_score", 0)
    brand = product.get("brand", "")
    affiliate_url = product.get("affiliate_url", "")
    description = product.get("description", f"Review of {name} — evidence-based analysis.")

    score_stars = min(5, max(1, round(score / 20)))
    pros = product.get("pros", [f"Strong performance in category"])
    cons = product.get("cons", ["Premium pricing", "Limited long-term data"])

    lines = [
        "---",
        f'title: "{name} — In-Depth Review"',
        f'description: "{description}"',
        f'category: "{category}"',
        f"price: {price}",
        f"rating: {score_stars}",
        "pros:",
    ]
    for p in pros[:5]:
        lines.append(f'  - "{p}"')
    lines.append("cons:")
    for c in cons[:5]:
        lines.append(f'  - "{c}"')
    if affiliate_url:
        lines.append(f'affiliateUrl: "{affiliate_url}"')
    if brand:
        lines.append(f'brand: "{brand}"')
    lines.append(f"publishedDate: {datetime.now(timezone.utc).strftime('%Y-%m-%d')}")
    lines.append("---\n")
    
    lines.extend([
        f"## {name} Review\n",
        f"{description}\n",
        f"**Opportunity Score:** {score:.1f}/100\n",
        f"**Category:** {category.replace('-', ' ').title()}\n",
        f"**Price:** ${price:,}\n\n",
        "## Key Specifications\n\n",
        "| Metric | Value |",
        "|--------|-------|",
        f"| Score | {score:.1f}/100 |",
        f"| Rating | ★ {score_stars}/5 |",
        f"| Category | {category.replace('-', ' ').title()} |\n\n",
        "## Pros & Cons\n\n",
        "### ✅ Pros\n",
    ])
    for p in pros[:5]:
        lines.append(f"- {p}")
    lines.extend(["\n### ❌ Cons\n"])
    for c in cons[:5]:
        lines.append(f"- {c}")
    
    lines.extend([
        "\n## Verdict\n\n",
        f"The **{name}** scores {score:.1f}/100 on our opportunity matrix. "
        f"This is a {'strong' if score > 80 else 'moderate'} opportunity "
        f"in the {category.replace('-', ' ')} space.\n",
        "\n*This is an auto-generated review from the Opportunity Scoring Engine. "
        "Review and update with real testing data before publishing.*\n",
    ])
    
    return "\n".join(lines), slug


def generate_guide_mdx(products: list, category: str) -> str:
    """Generate a buyer's guide MDX from multiple products in same category."""
    cat_name = category.replace("-", " ").title()
    
    lines = [
        "---",
        f'title: "The Complete Buyer\'s Guide to {cat_name} ({datetime.now().year})"',
        f'description: "Compare the best {category.replace("-", " ")} products. Evidence-based buying advice for biohackers."',
        f'category: "{category}"',
        f"products: {len(products)}",
        f"publishedDate: {datetime.now(timezone.utc).strftime('%Y-%m-%d')}",
        "---\n",
        f"# The Complete Buyer's Guide to {cat_name}\n",
        f"Comparing **{len(products)}** top products in the {cat_name.lower()} space.\n\n",
        "## How to Choose\n\n",
        "### Key Factors to Consider\n",
        "1. **Research backing** — Has the technology been validated in peer-reviewed studies?\n",
        "2. **Build quality** — Is the device well-constructed for daily use?\n",
        "3. **Warranty & support** — What happens if it breaks?\n",
        "4. **Price vs performance** — Are you paying for a brand name or real engineering?\n\n",
        "## Top Picks\n\n",
        "| Product | Score | Price |",
        "|---------|-------|-------|",
    ]
    
    for p in sorted(products, key=lambda x: x.get("_score", 0), reverse=True):
        name = p.get("name", "Product")
        score = p.get("_score", 0)
        price = p.get("price", 0)
        lines.append(f"| [{name}](#) | {score:.1f} | ${price:,} |")
    
    lines.extend([
        "\n*This guide was auto-generated by the Opportunity Scoring Engine. "
        "Review and update with real testing data before publishing.*\n",
    ])
    
    return "\n".join(lines)


def load_passed_products() -> list:
    """Load all products that passed the scoring threshold."""
    products = []
    if SCORER_OUTPUT.exists():
        for f in SCORER_OUTPUT.glob("*.json"):
            try:
                with open(f) as fp:
                    products.append(json.load(fp))
            except json.JSONDecodeError:
                print(f"  ⚠ Invalid JSON: {f}", file=sys.stderr)
    return products


def publish_reviews(products: list):
    """Write product reviews to Astro content directory."""
    reviews_dir = BLOG_CONTENT_DIR / "reviews"
    reviews_dir.mkdir(parents=True, exist_ok=True)
    
    count = 0
    for product in products:
        mdx, slug = generate_review_mdx(product)
        filepath = reviews_dir / f"{slug}.md"
        if not filepath.exists():
            with open(filepath, "w") as f:
                f.write(mdx)
            print(f"  ✍ Created: {filepath.name}")
            count += 1
        else:
            print(f"  ⏭ Skipped (exists): {filepath.name}")
    
    return count


def publish_guides(products: list):
    """Group products by category and write buyer's guides."""
    guides_dir = BLOG_CONTENT_DIR / "guides"
    guides_dir.mkdir(parents=True, exist_ok=True)
    
    # Group by category
    by_category = {}
    for p in products:
        cat = CATEGORY_MAP.get(p.get("_category", ""), "other")
        if cat not in by_category:
            by_category[cat] = []
        by_category[cat].append(p)
    
    count = 0
    for category, cat_products in by_category.items():
        if len(cat_products) < 2:
            continue
        mdx = generate_guide_mdx(cat_products, category)
        slug = f"buying-guide-{category}"
        filepath = guides_dir / f"{slug}.md"
        if not filepath.exists():
            with open(filepath, "w") as f:
                f.write(mdx)
            print(f"  ✍ Created guide: {filepath.name} ({len(cat_products)} products)")
            count += 1
    
    return count


def main():
    parser = argparse.ArgumentParser(description="Scoring Engine → Blog Pipeline")
    parser.add_argument("--products", type=str, help="JSON file with scored products")
    parser.add_argument("--score-all", action="store_true", help="Run scorer on all batch items first")
    parser.add_argument("--input-dir", type=str, default=str(SCORER_INPUT),
                        help="Directory with batch input JSONs")
    args = parser.parse_args()

    products = []
    
    if args.score_all:
        if not SCORER_INPUT.exists():
            print(f"❌ Input directory not found: {SCORER_INPUT}")
            sys.exit(1)
        for batch_file in SCORER_INPUT.glob("*.json"):
            print(f"  Scoring: {batch_file.name}")
            result = subprocess.run(
                ["python3", str(SCORER_PATH), "--batch", str(batch_file), "--no-save"],
                capture_output=True, text=True
            )
            print(result.stdout[-500:] if len(result.stdout) > 500 else result.stdout)
        
        products = load_passed_products()
    
    elif args.products:
        with open(args.products) as f:
            products = json.load(f)
    else:
        products = load_passed_products()
    
    if not products:
        print("📭 No passing products found (threshold > 80). Nothing to publish.")
        print(f"   Check: {SCORER_OUTPUT}/ for scored products.")
        return
    
    print(f"\n📦 Publishing {len(products)} passing products to blog...")
    
    # Publish reviews
    reviews_count = publish_reviews(products)
    guides_count = publish_guides(products)
    
    print(f"\n✅ Published: {reviews_count} reviews, {guides_count} guides")
    print(f"   Location: {BLOG_CONTENT_DIR}")
    print(f"\n🚀 Next: cd /opt/data/affiliate-blog && npm run build")


if __name__ == "__main__":
    SCORER_INPUT = SCORER_BATCH
    main()
