#!/usr/bin/env python3
"""Search Amazon via Apify for weighted blankets by brand."""

import os, json, sys
from datetime import timedelta
from apify_client import ApifyClient

API_KEY=os.environ.get("APIFY_API_KEY")
if not API_KEY:
    print("ERROR: APIFY_API_KEY not set", file=sys.stderr)
    sys.exit(1)

OUTPUT_FILE = "/opt/data/affiliate-blog/scripts/weighted_blanket_products.json"

BRANDS = [
    "Gravity Blanket", "Luna Weighted Blanket", "Baloo",
    "Quility", "YnM", "Bearaby", "ZonLi",
    "Utopia Bedding", "SensaCalm",
]

AFFILIATE_TAG = "sciencesolved-20"

def build_affiliate_url(asin):
    return f"https://www.amazon.com/dp/{asin}?tag={AFFILIATE_TAG}"

def main():
    client = ApifyClient(API_KEY)
    all_products = []

    actors = [
        "jungle_scout/amazon_product_scraper",
        "vaclavrut/amazon-scraper",
        "taishikato/amazon-scraper",
    ]

    for brand in BRANDS:
        print(f"\n--- Searching: {brand} ---")
        run_input = {
            "searchTerms": [f"{brand} weighted blanket"],
            "maxResults": 5,
            "country": "US",
            "currency": "USD",
        }
        success = False

        for actor_name in actors:
            if success:
                break
            try:
                print(f"  Actor: {actor_name}")
                run = client.actor(actor_name).call(
                    run_input=run_input,
                    wait_duration=timedelta(seconds=90),
                )
                dataset_id = run.get("defaultDatasetId")
                if not dataset_id:
                    continue
                items = client.dataset(dataset_id).list_items().items
                print(f"  Found {len(items)} products")
                for item in items:
                    asin = item.get("asin") or item.get("ASIN")
                    if not asin:
                        continue
                    product = {
                        "asin": asin,
                        "title": item.get("title") or item.get("productName") or item.get("name"),
                        "price": item.get("price") or item.get("ourPrice") or item.get("priceValue") or item.get("listPrice"),
                        "rating": item.get("rating") or item.get("stars") or item.get("averageRating"),
                        "features": item.get("features") or item.get("featureBullets") or item.get("highlights"),
                        "affiliate_link": build_affiliate_url(asin),
                        "brand": brand,
                    }
                    product = {k: v for k, v in product.items() if v is not None}
                    all_products.append(product)
                    t = str(product.get("title", "N/A"))[:60]
                    print(f"    {product.get('asin')} - {t}")
                if items:
                    success = True
            except Exception as e:
                print(f"    Failed: {type(e).__name__}: {e}")

        if not success:
            print(f"  No results for {brand}")

    # Deduplicate
    seen = set()
    unique = []
    for p in all_products:
        if p["asin"] not in seen:
            seen.add(p["asin"])
            unique.append(p)

    output = {
        "source": "Amazon via Apify",
        "affiliate_tag": AFFILIATE_TAG,
        "total_products": len(unique),
        "products": unique,
    }

    os.makedirs(os.path.dirname(OUTPUT_FILE), exist_ok=True)
    with open(OUTPUT_FILE, "w") as f:
        json.dump(output, f, indent=2)

    print(f"\nSaved {len(unique)} unique products to {OUTPUT_FILE}")
    for p in unique:
        print(f"\n  ASIN: {p['asin']} | Brand: {p.get('brand','?')} | Price: {p.get('price','?')} | Rating: {p.get('rating','?')}")

if __name__ == "__main__":
    main()
