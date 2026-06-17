"""
Content pipeline: offer data → LLM draft → markdown article.
"""

from __future__ import annotations
import json, os, textwrap
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional
from config import AffiliateOffer, load_config, logger


class ContentPipeline:
    """Generate review articles from affiliate offer data."""

    def __init__(self, config: dict = None):
        self.config = config or load_config()
        pubs = self.config.get("publishing", {})
        self.output_dir = Path(pubs.get("output_dir", "../content/reviews"))
        self.disclosure_text = pubs.get(
            "disclosure_text",
            "We earn a commission if you purchase through our links, at no extra cost to you."
        )
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def build_system_prompt(self) -> str:
        """System prompt for the LLM reviewer."""
        return textwrap.dedent("""
        You are an expert product reviewer for Science Solved It, a biohacking
        hardware review site. You write evidence-based, data-driven reviews
        that help readers make informed purchasing decisions.

        Style guidelines:
        - Start with a 2-3 sentence quick verdict (most-read part)
        - Use bullet points for pros/cons
        - Include specific specs and benchmarks
        - Compare against 2-3 competitors
        - Cite scientific evidence where relevant
        - Write 800-1500 words
        - Natural, authoritative tone — not hype, not dry
        - Include a clear "Who should buy this" section
        - End with a bottom-line recommendation

        Your output will be a complete markdown file with YAML frontmatter.
        """).strip()

    def build_user_prompt(self, offer: AffiliateOffer) -> str:
        """Build the prompt for a single offer."""
        return textwrap.dedent(f"""
        Write a product review for the following product.

        Network: {offer.network}
        Product: {offer.program_name}
        Brand: {offer.advertiser}
        Category: {offer.category}
        Price: ${offer.price if offer.price else 'N/A'}
        Description: {offer.description}
        Commission: {offer.commission_value}{'%' if offer.commission_type == 'percentage' else '$'}
        Cookie duration: {offer.cookie_days} days
        Geo: {', '.join(offer.geo_targets)}

        Generate a complete markdown file with YAML frontmatter containing:
        - title
        - description (meta)
        - category
        - price (number)
        - rating (number 1-5)
        - pros (array)
        - cons (array)
        - brand
        - affiliateUrl (use: {offer.tracking_link or offer.deeplink})
        - publishedDate (today)
        - featured (false)
        - specs (key-value pairs)
        - faq (array of q/a pairs)

        Then the body content in markdown with sections:
        ## Quick Verdict
        ## What We Tested
        ## Performance
        ## Build Quality
        ## Pros & Cons (summary)
        ## How It Compares
        ## Who Should Buy This
        ## The Competition
        ## FAQ
        ## Bottom Line
        """).strip()

    def generate_article(self, offer: AffiliateOffer) -> str:
        """
        Generate a full markdown article for an offer.
        In production this calls an LLM. For now, returns a template.
        """
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        slug = self._make_slug(offer.program_name)
        today_iso = datetime.now(timezone.utc).strftime("%Y-%m-%dT00:00:00.000Z")

        article = textwrap.dedent(f"""---
title: "{offer.program_name} Review: {offer.description[:60]}"
description: "{offer.description[:150]}"
category: "{offer.category}"
price: {int(offer.price) if offer.price else 0}
rating: 4.0
pros:
  - "TBD — add verified pros here"
cons:
  - "TBD — add verified cons here"
affiliateUrl: "{offer.tracking_link or offer.deeplink or ''}"
brand: "{offer.advertiser}"
publishedDate: {today_iso}
featured: false
image: "/images/placeholder.png"
specs: {{}}
faq: []
---

## Quick Verdict

The **{offer.program_name}** by {offer.advertiser} is a {'${:,.0f}'.format(offer.price) if offer.price else ''} device in the {offer.category.replace('-', ' ')} space. {'Commission: ' + str(offer.commission_value) + ('%' if offer.commission_type == 'percentage' else '$') + ' with ' + str(offer.cookie_days) + '-day cookie.' if offer.commission_value else ''}

*Full review coming soon — this page will be updated with hands-on testing data, verified specs, and comparison benchmarks.*

## What We Tested

*Testing in progress.*

## Pros & Cons

**Pros**
- TBD

**Cons**
- TBD

## Who Should Buy This

TBD

## Where to Buy

[Check latest price on {offer.advertiser}]({offer.tracking_link or offer.deeplink or '#'}) — affiliate link, we may earn a commission.

*{self.disclosure_text}*
""").strip()

        return article

    def save_article(self, offer: AffiliateOffer, content: str, dry_run: bool = False) -> Optional[str]:
        """Save the generated article as a markdown file."""
        slug = self._make_slug(offer.program_name)
        filename = f"{slug}.md"
        filepath = self.output_dir / filename

        if dry_run:
            logger.info(f"[DRY RUN] Would write: {filepath}")
            return None

        with open(filepath, "w") as f:
            f.write(content)
        logger.info(f"Article saved: {filepath}")
        return str(filepath)

    def _make_slug(self, name: str) -> str:
        """Convert product name to URL-safe slug."""
        slug = name.lower().strip()
        slug = slug.replace(" ", "-")
        slug = "".join(c for c in slug if c.isalnum() or c == "-")
        slug = slug.strip("-")
        return slug[:80]
