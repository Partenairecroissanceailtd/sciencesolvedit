#!/usr/bin/env python3
"""Scrape Amazon products via Apify for a given niche."""
import json, os, sys, time, urllib.request

# Load .env
env_path = os.path.join(os.path.dirname(__file__), "affiliate_pipeline", ".env")
if os.path.exists(env_path):
    for line in open(env_path):
        line = line.strip()
        if "=" in line and not line.startswith("#"):
            k, v = line.split("=", 1)
            os.environ[k.strip()] = v.strip().strip('"').strip("'")

APIFY_TOKEN = os.environ.get("APIFY_API_KEY", "").strip()
if not APIFY_TOKEN or APIFY_TOKEN == "apify_...":
    print("ERROR: No valid APIFY_API_KEY in .env")
    sys.exit(1)

QUERY = sys.argv[1] if len(sys.argv) > 1 else "cold plunge tub ice bath"
ACTOR = "junglee~free-amazon-product-scraper"
API_URL = f"https://api.apify.com/v2/acts/{ACTOR}/run-sync-get-dataset-items?token={APIFY_TOKEN}"

print(f"Searching Amazon for: {QUERY}", flush=True)

payload = {
    "categoryUrls": [{"url": f"https://www.amazon.com/s?k={QUERY.replace(' ', '+')}"}],
    "maxItemsPerStartUrl": 15,
    "maxSearchPagesPerStartUrl": 1,
    "maxProductVariantsAsSeparateResults": 0,
}

req = urllib.request.Request(
    API_URL,
    data=json.dumps(payload).encode(),
    headers={"Content-Type": "application/json"},
    method="POST",
)
try:
    with urllib.request.urlopen(req, timeout=180) as resp:
        data = json.loads(resp.read().decode())
except Exception as e:
    print(f"ERROR: {e}")
    sys.exit(1)

if not data:
    print("No results returned")
    sys.exit(1)

print(f"\n=== TOP {min(10, len(data))} PRODUCTS ===")
products = []
for item in data[:10]:
    asin = item.get("asin", "")
    title = item.get("title", item.get("productName", ""))
    if not asin or not title:
        continue
    rating = item.get("rating", {})
    rating_val = ""
    review_count = ""
    if isinstance(rating, dict):
        rating_val = rating.get("average", "")
        review_count = rating.get("count", "")
    elif isinstance(rating, str):
        rating_val = rating
    
    price_raw = item.get("price", {})
    price_str = ""
    if isinstance(price_raw, dict):
        price_str = price_raw.get("value", price_raw.get("raw", ""))
    else:
        price_str = str(price_raw)
    
    features = item.get("features", item.get("featureBullets", []))
    if isinstance(features, str):
        features = [features]
    
    description = item.get("description", item.get("productDescription", ""))
    if isinstance(description, str):
        description = description[:200]
    
    main_image = item.get("mainImage", item.get("images", ""))
    if isinstance(main_image, list) and main_image:
        main_image = main_image[0] if isinstance(main_image[0], str) else (main_image[0].get("url", "") if isinstance(main_image[0], dict) else "")
    elif isinstance(main_image, dict):
        main_image = main_image.get("url", "")
    
    affiliate_link = f"https://www.amazon.com/dp/{asin}?tag=sciencesolved-20"
    
    p = {
        "asin": asin,
        "title": title,
        "price": price_str,
        "rating": rating_val,
        "reviews": review_count,
        "features": features[:5] if features else [],
        "description": description if description else title,
        "affiliate_link": affiliate_link,
        "image": main_image,
    }
    products.append(p)
    
    star_str = "⭐" * (int(float(rating_val)) if rating_val else 0)
    print(f"\n{star_str} {title}")
    print(f"   ASIN: {asin}")
    print(f"   Price: {price_str} | Rating: {rating_val}/5 ({review_count} reviews)")
    print(f"   Link: {affiliate_link}")

# Save to JSON for next step
out = os.path.join(os.path.dirname(__file__), "cold_plunge_products.json")
with open(out, "w") as f:
    json.dump(products, f, indent=2)
print(f"\n✅ Saved {len(products)} products to {out}")
