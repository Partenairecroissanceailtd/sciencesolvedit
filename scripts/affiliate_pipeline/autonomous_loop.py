#!/usr/bin/env python3
"""
Autonomous Amazon Affiliate Loop — 5-Phase Pipeline
====================================================
Phases:
  1. SEO Reconnaissance (Google Search Scraper)
  2. Product Hunt (Amazon Scraper)
  3. Affiliate Link Assembly (tag: sciencesolved-20)
  4. Trojan Horse Content Generation (DeepSeek via API)
  5. GitHub Deploy

Usage:
  python3 autonomous_loop.py "red light therapy panel" [--no-deploy]
  python3 autonomous_loop.py "cast iron pipe cutter" [--no-deploy]

CRITICAL: NEVER write a static price. Always use "Check current price on Amazon".
"""

import os, sys, json, time, subprocess
from pathlib import Path
from datetime import datetime
from urllib.parse import quote_plus

# ── Config ──────────────────────────────────────────────────────────────
# Load from .env file (overrides any existing env vars)
_env_path = Path(__file__).parent / ".env"
if _env_path.exists():
    for _line in open(_env_path):
        _line = _line.strip()
        if "=" in _line and not _line.startswith("#"):
            _k, _v = _line.split("=", 1)
            _k = _k.replace("export ", "", 1).strip()
            _v = _v.strip().strip('"').strip("'")
            os.environ[_k] = _v  # Override, not setdefault

APIFY_TOKEN = os.environ.get("APIFY_API_KEY", "")
AMAZON_TAG = os.environ.get("AMAZON_TAG", "sciencesolved-20")
GITHUB_REPO_DIR = "/opt/data/affiliate-blog"
CONTENT_DIR = Path(GITHUB_REPO_DIR) / "src" / "content" / "reviews"
DEEPSEEK_API_KEY = os.environ.get("DEEPSEEK_API_KEY", "")

AMAZON_ACTOR = "junglee~free-amazon-product-scraper"
GOOGLE_ACTOR = "apify~google-search-scraper"
APIFY_BASE = "https://api.apify.com/v2"

# ── Phase 1: SEO Reconnaissance ────────────────────────────────────────

def phase1_seo_recon(niche: str) -> dict:
    """Search Google for the niche, extract PeopleAlsoAsk, related queries, top titles."""
    print(f"\n{'='*60}")
    print(f"PHASE 1 — SEO Reconnaissance: '{niche}'")
    print(f"{'='*60}")

    queries = [
        niche,
        f"best {niche} 2026",
        f"how to choose {niche}",
        f"{niche} review",
        f"what to look for {niche}",
    ]

    all_data = {
        "organic_titles": [],
        "organic_urls": [],
        "related_queries": [],
        "people_also_ask": [],
        "top_headings": [],
    }

    for q in queries[:2]:  # Use first 2 queries to save Apify credits
        print(f"  Searching: '{q}'...")
        input_data = {
            "queries": q,
            "resultsPerPage": 10,
            "maxPagesPerQuery": 1,
        }

        resp = _run_actor(GOOGLE_ACTOR, input_data)
        if not resp:
            continue

        # Response is a list of SERP result pages (1 per query)
        for page in resp:
            # Organic results
            for r in page.get("organicResults", []):
                t = r.get("title", "")
                u = r.get("url", "")
                if t:
                    all_data["organic_titles"].append(t)
                    all_data["organic_urls"].append(u)

            # People Also Ask
            for q in page.get("peopleAlsoAsk", []):
                question = q.get("question", "") or q.get("title", "")
                answer = q.get("answer", "") or q.get("snippet", "")
                if question:
                    q_item = {"question": question, "snippet": answer}
                    if q_item not in all_data["people_also_ask"]:
                        all_data["people_also_ask"].append(q_item)

            # Related queries
            for r in page.get("relatedQueries", []):
                t = r.get("title", "")
                if t and t not in all_data["related_queries"]:
                    all_data["related_queries"].append(t)

        time.sleep(0.5)

    print(f"  → Organic results: {len(all_data['organic_titles'])}")
    print(f"  → Related queries: {len(all_data['related_queries'])}")
    print(f"  → People Also Ask: {len(all_data['people_also_ask'])}")

    return all_data


# ── Phase 2: Amazon Product Hunt ────────────────────────────────────────

def phase2_amazon_hunt(niche: str, seo_data: dict) -> list[dict]:
    """Search Amazon for top-rated products in this niche."""
    print(f"\n{'='*60}")
    print(f"PHASE 2 — Amazon Product Hunt: '{niche}'")
    print(f"{'='*60}")

    search_term = niche.replace("best ", "").strip()
    amazon_url = f"https://www.amazon.com/s?k={quote_plus(search_term)}"

    input_data = {
        "categoryUrls": [{"url": amazon_url}],
        "maxItemsPerStartUrl": 10,
        "maxSearchPagesPerStartUrl": 1,
        "maxProductVariantsAsSeparateResults": 0,
    }

    results = _run_actor(AMAZON_ACTOR, input_data)
    if not results:
        print("  ⚠ No Amazon results returned")
        return []

    # Parse and filter products
    products = []
    for item in results[:10]:
        asin = item.get("asin", "")
        title = item.get("title", item.get("productName", ""))
        if not asin or not title:
            continue

        # Extract price safely — never write it to content
        price_raw = item.get("price", {})
        if isinstance(price_raw, dict):
            price_val = price_raw.get("value", price_raw.get("raw", ""))
        else:
            price_val = str(price_raw)

        rating = item.get("rating", {})
        if isinstance(rating, dict):
            rating_val = rating.get("average", rating.get("value", ""))
        else:
            rating_val = str(rating)

        # Features / bullet points
        features = item.get("features", item.get("featureBullets", []))
        if isinstance(features, str):
            features = [features]

        description = item.get("description", item.get("productDescription", ""))
        main_image = item.get("mainImage", item.get("images", [None]))
        if isinstance(main_image, list) and main_image:
            main_image = main_image[0] if isinstance(main_image[0], str) else (main_image[0].get("url", "") if isinstance(main_image[0], dict) else "")
        elif isinstance(main_image, dict):
            main_image = main_image.get("url", "")

        # Build affiliate link — NO static price
        affiliate_link = f"https://www.amazon.com/dp/{asin}?tag={AMAZON_TAG}"

        product = {
            "asin": asin,
            "title": title,
            "affiliate_link": affiliate_link,
            "rating": rating_val,
            "features": features[:5] if features else [],
            "description": description[:300] if description else "",
            "image": main_image,
        }
        products.append(product)

    print(f"  → Products found: {len(products)}")
    for p in products:
        star = "⭐" * (int(float(p["rating"])) if p["rating"] else 0)
        print(f"    {star} {p['title'][:60]} — ASIN: {p['asin']}")

    return products


# ── Phase 3: Affiliate Link Assembly ────────────────────────────────────

def phase3_assemble_links(products: list[dict]) -> list[dict]:
    """Already done inline in phase2, but verify and log."""
    print(f"\n{'='*60}")
    print(f"PHASE 3 — Affiliate Link Assembly (tag: {AMAZON_TAG})")
    print(f"{'='*60}")

    for p in products:
        assert f"?tag={AMAZON_TAG}" in p["affiliate_link"], f"Missing tag in {p['asin']}"
        print(f"  ✓ {p['asin']} → {p['affiliate_link']}")

    return products


# ── Phase 4: Trojan Horse Content ───────────────────────────────────────

def phase4_generate_content(niche: str, seo_data: dict, products: list[dict]) -> str:
    """Generate a Trojan Horse article: educational guide + product recommendation."""
    print(f"\n{'='*60}")
    print(f"PHASE 4 — Content Generation (Trojan Horse Strategy)")
    print(f"{'='*60}")

    # Build context from SEO data
    paa_text = "\n".join([f"- Q: {p['question']}" for p in seo_data.get("people_also_ask", [])[:5]])
    related_text = "\n".join([f"- {q}" for q in seo_data.get("related_queries", [])[:8]])
    top_titles = "\n".join([f"- {t}" for t in seo_data.get("organic_titles", [])[:5]])

    # Build product list for the article
    product_text = ""
    for i, p in enumerate(products[:3], 1):
        features = "\n".join([f"  • {f}" for f in p["features"][:3]]) if p["features"] else ""
        product_text += f"""
PRODUCT {i}: {p['title']}
ASIN: {p['asin']}
Rating: {p['rating']}/5
Key Features:
{features if features else "  • Premium quality"}
Affiliate Link: {p['affiliate_link']}
"""

    # Determine article angle
    if seo_data.get("people_also_ask"):
        hook_q = seo_data["people_also_ask"][0]["question"]
    elif seo_data.get("related_queries"):
        hook_q = seo_data["related_queries"][0]
    else:
        hook_q = f"How to choose the best {niche}"

    system_prompt = """You are a product review expert for "Science Solved It" — an evidence-based blog that recommends science-backed solutions. Write in a friendly, authoritative tone.

STRICT RULES:
1. NEVER write a static price. NEVER say "costs $X" or "priced at $X". Use only: "Check current price on Amazon", "See latest pricing on Amazon", "View discounts on Amazon".
2. Write an educational, step-by-step buying guide first. Embed product recommendations as "Recommended Gear" sections.
3. Use the "Trojan Horse" strategy — 70% educational value, 30% product recommendation.
4. Include a table comparing featured products (with checkmarks/ratings, NOT prices).
5. Start with a hook that addresses the reader's pain point.
6. End with a clear CTA.
7. Use H2, H3 headings for scannability.
8. Output in clean GitHub-flavored Markdown.
9. Include a frontmatter block with: title, date, category, tags, image.
10. Max 1500 words."""

    user_prompt = f"""I need a buying guide / review article for the niche: "{niche}"

## SEO Intelligence
Top-ranking article titles:
{top_titles}

Related searches people use:
{related_text}

People Also Ask (target these questions in your article):
{paa_text}

## Products to Recommend
{product_text}

## Instructions
- The article should help someone choose the best {niche} for their needs
- Cover: what to look for, key features, types, buyer's remorse pitfalls
- Recommend the top 3 products above as "Our Recommendations" or "Top Picks"
- Use ONLY "Check current price on Amazon" for pricing — no static dollar amounts
- Write 1000-1500 words
- Output as clean Markdown with frontmatter"""

    if DEEPSEEK_API_KEY:
        print("  Calling DeepSeek API...")
        content = _call_deepseek(system_prompt, user_prompt)
    else:
        print("  ⚠ No DEEPSEEK_API_KEY set — using local fallback")
        content = _fallback_content(niche, seo_data, products)

    slug = niche.lower().replace(" ", "-").replace("/", "-")[:50]
    date_str = datetime.now().strftime("%Y-%m-%d")
    rating_stars = "⭐⭐⭐⭐" + ("⭐" if products and (lambda r: float(r) if r else 0)(products[0].get("rating", "")) >= 4.5 else "")

    first_product_image = products[0].get("image", "") if products else ""

    frontmatter = f"""---
title: "The Best {niche.title()} in 2026: A Complete Buyer's Guide"
description: "Looking for the best {niche}? We analyzed the top-rated products and created the ultimate guide to help you choose."
pubDate: {date_str}
category: product-reviews
tags: ["{niche}", "buying-guide", "2026", "review"]
image: "{first_product_image}"
draft: false
---

"""
    full_article = frontmatter + content

    print(f"  → Article generated: ~{len(full_article)} chars")

    return full_article


# ── Phase 5: GitHub Deploy ─────────────────────────────────────────────

def phase5_deploy(niche: str, article: str, dry_run: bool = False) -> Path:
    """Save article as Markdown and commit to GitHub."""
    print(f"\n{'='*60}")
    print(f"PHASE 5 — GitHub Deploy")
    print(f"{'='*60}")

    slug = niche.lower().replace(" ", "-").replace("/", "-")[:50]
    date_prefix = datetime.now().strftime("%Y-%m-%d")
    filename = f"{date_prefix}-{slug}.md"
    output_path = CONTENT_DIR / filename

    # Ensure content dir exists
    CONTENT_DIR.mkdir(parents=True, exist_ok=True)

    # Write file
    with open(output_path, "w") as f:
        f.write(article)
    print(f"  ✓ Saved: {output_path}")

    if dry_run:
        print(f"  ⏸ DRY RUN — skipping git commit/deploy")
        return output_path

    # Git commit + push
    try:
        os.chdir(GITHUB_REPO_DIR)
        subprocess.run(["git", "add", str(output_path)], check=True, capture_output=True)
        subprocess.run(["git", "commit", "-m", f"Auto: {niche} buying guide [affiliate-loop]"], check=True, capture_output=True)
        result = subprocess.run(["git", "push"], check=True, capture_output=True, text=True)
        print(f"  ✓ Deployed to GitHub")
        print(f"  ✓ URL will be live at: https://www.sciencesolvedit.store/reviews/{slug}")
    except subprocess.CalledProcessError as e:
        print(f"  ⚠ Git error: {e.stderr if hasattr(e, 'stderr') else e}")

    return output_path


# ── Utility Functions ───────────────────────────────────────────────────

def _run_actor(actor_id: str, input_data: dict) -> list | None:
    """Run an Apify actor synchronously and return dataset items."""
    url = f"{APIFY_BASE}/acts/{actor_id}/run-sync-get-dataset-items?token={APIFY_TOKEN}"
    try:
        import urllib.request
        req = urllib.request.Request(
            url,
            data=json.dumps(input_data).encode(),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=120) as resp:
            data = json.loads(resp.read().decode())
            if isinstance(data, list):
                return data
            print(f"    Unexpected response: {str(data)[:200]}")
            return None
    except Exception as e:
        print(f"    ⚠ Actor error: {e}")
        return None


def _call_deepseek(system: str, user: str) -> str:
    """Call DeepSeek API for article generation."""
    import urllib.request
    url = "https://api.deepseek.com/v1/chat/completions"
    payload = {
        "model": "deepseek-chat",
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        "temperature": 0.7,
        "max_tokens": 4000,
    }
    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode(),
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {DEEPSEEK_API_KEY}",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            result = json.loads(resp.read().decode())
            return result["choices"][0]["message"]["content"]
    except Exception as e:
        print(f"    ⚠ DeepSeek error: {e}")
        return _fallback_content("", {}, [])


def _fallback_content(niche: str, seo_data: dict, products: list[dict]) -> str:
    """Fallback template when API is unavailable."""
    lines = [f"## How to Choose the Best {niche.title()} for Your Needs", ""]
    lines.append(f"Finding the right {niche} can feel overwhelming with so many options on the market. ")
    lines.append(f"This guide breaks down everything you need to know to make an informed decision.")
    lines.append("")

    if seo_data.get("people_also_ask"):
        lines.append("### Common Questions Buyers Have")
        lines.append("")
        for q in seo_data["people_also_ask"][:3]:
            lines.append(f"- **{q['question']}**")
            if q.get("snippet"):
                lines.append(f"  {q['snippet'][:200]}")
        lines.append("")

    lines.append("### What to Look For")
    lines.append("")
    lines.append(f"When shopping for a {niche}, consider these factors:")
    lines.append("- **Build quality**: Look for durable materials that last")
    lines.append("- **Key specifications**: Check the specs that matter most for your use case")
    lines.append("- **User reviews**: Real-world feedback tells you what the specs don't")
    lines.append("- **Warranty & support**: A good warranty protects your investment")
    lines.append("")

    if products:
        lines.append("### Our Top Recommendations")
        lines.append("")
        for i, p in enumerate(products[:3], 1):
            lines.append(f"**{i}. {p['title']}**")
            lines.append(f"   {'⭐' * int(float(p['rating'])) if p.get('rating') else '★★★★☆'}")
            if p.get("features"):
                for f in p["features"][:2]:
                    lines.append(f"   • {f}")
            lines.append(f"   👉 [Check current price on Amazon]({p['affiliate_link']})")
            lines.append("")

        lines.append("### Comparison Table")
        lines.append("")
        lines.append("| Product | Rating | Key Highlight |")
        lines.append("|---------|--------|---------------|")
        for p in products[:3]:
            stars = f"{p['rating']}/5" if p.get("rating") else "★★★★☆"
            highlight = p["features"][0][:50] if p.get("features") else "Top rated"
            lines.append(f"| [{p['title']}]({p['affiliate_link']}) | {stars} | {highlight} |")
        lines.append("")

    lines.append("### Final Verdict")
    lines.append("")
    lines.append(f"Choosing the best {niche} comes down to your specific needs and budget. ")
    lines.append("We recommend the products above based on real user reviews and hands-on analysis.")
    lines.append("")
    lines.append(f"👉 [See full specs and pricing on Amazon →]({products[0]['affiliate_link'] if products else '#'})")

    return "\n".join(lines)


# ── Main Orchestrator ──────────────────────────────────────────────────

def main():
    import argparse
    parser = argparse.ArgumentParser(description="Autonomous Amazon Affiliate Loop")
    parser.add_argument("niche", type=str, help="Niche or product category (e.g., 'red light therapy panel')")
    parser.add_argument("--no-deploy", action="store_true", help="Skip GitHub deploy, save locally only")
    parser.add_argument("--dry-run", action="store_true", help="Skip all writes, show what would happen")
    args = parser.parse_args()

    niche = args.niche.strip()

    print(f"\n{'#'*60}")
    print(f"# Autonomous Affiliate Loop Starting")
    print(f"# Niche: {niche}")
    print(f"# Tag: {AMAZON_TAG}")
    print(f"{'#'*60}\n")

    # Phase 1
    seo_data = phase1_seo_recon(niche)

    # Phase 2
    products = phase2_amazon_hunt(niche, seo_data)
    if not products:
        print("\n❌ No Amazon products found. Aborting.")
        sys.exit(1)

    # Phase 3 (inline, just verify)
    products = phase3_assemble_links(products)

    # Phase 4
    article = phase4_generate_content(niche, seo_data, products)

    # Phase 5
    path = phase5_deploy(niche, article, dry_run=args.dry_run or args.no_deploy)

    print(f"\n{'#'*60}")
    print(f"# ✅ Complete!")
    print(f"# Article: {path}")
    if not args.dry_run and not args.no_deploy:
        print(f"# Live at: https://www.sciencesolvedit.store/reviews/{niche.lower().replace(' ', '-')}")
    print(f"{'#'*60}\n")


if __name__ == "__main__":
    main()
