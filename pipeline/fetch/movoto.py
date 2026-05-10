"""Movoto.com listing scraper.

Movoto has been the most reliable of the listing aggregators in our
testing — Zillow / Redfin / Realtor.com / HAR all 403 generic clients
on a regular basis. Movoto generally lets through requests with
realistic browser headers.

Strategy:
1. Search by address → resolve to canonical listing URL
2. Fetch listing page → save raw HTML to wiki/raw/<slug>.html
3. Extract a few high-confidence fields with regex (price, beds, baths,
   sqft) — anything more nuanced is left for the LLM extraction layer

The raw HTML on disk is the durable artifact. Even when extraction
heuristics drift, the LLM can re-process the saved HTML.
"""
from __future__ import annotations

import re
from pathlib import Path
from urllib.parse import quote_plus

import httpx

from pipeline.common.address import Address
from pipeline.fetch.base import Fact, FetchResult, Source

MOVOTO_SEARCH = "https://www.movoto.com/search/?searchType=forsale&q={q}"
DEFAULT_RAW_DIR = Path(__file__).resolve().parent.parent.parent / "wiki" / "raw"

# Realistic Chrome-on-macOS UA. Avoids the "python-httpx/X.Y" default that
# everyone blocks.
BROWSER_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_5) AppleWebKit/605.1.15 "
        "(KHTML, like Gecko) Version/17.5 Safari/605.1.15"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    # No Brotli — httpx needs a separate brotli package to decompress 'br'.
    # gzip/deflate cover ~all CDN responses fine.
    "Accept-Encoding": "gzip, deflate",
    "Cache-Control": "no-cache",
    "Pragma": "no-cache",
    "Sec-Fetch-Dest": "document",
    "Sec-Fetch-Mode": "navigate",
    "Sec-Fetch-Site": "none",
    "Sec-Fetch-User": "?1",
    "Upgrade-Insecure-Requests": "1",
}


def _extract_first_match(pattern: str, html: str) -> str | None:
    m = re.search(pattern, html, re.IGNORECASE | re.DOTALL)
    return m.group(1).strip() if m else None


def _to_int(s: str | None) -> int | None:
    if s is None:
        return None
    digits = re.sub(r"[^\d]", "", s)
    return int(digits) if digits else None


def _to_float(s: str | None) -> float | None:
    if s is None:
        return None
    cleaned = re.sub(r"[^\d.]", "", s)
    try:
        return float(cleaned)
    except (TypeError, ValueError):
        return None


class MovotoSource(Source):
    name = "movoto"

    def __init__(self, raw_dir: Path = DEFAULT_RAW_DIR, listing_url: str | None = None):
        self.raw_dir = raw_dir
        self.listing_url_override = listing_url

    def fetch(self, address: Address) -> FetchResult:
        listing_url = self.listing_url_override or self._find_listing_url(address)
        if listing_url is None:
            return FetchResult(
                source_name=self.name,
                address=address,
                facts={},
                error=(
                    "No Movoto listing found. Movoto's search API is JS-rendered and "
                    "rejects HTTP clients. Pass --movoto-url <listing-url> to bypass, or "
                    "find the URL manually via Google `site:movoto.com \"<address>\"`."
                ),
            )

        try:
            r = httpx.get(listing_url, headers=BROWSER_HEADERS, timeout=30.0,
                          follow_redirects=True)
            if r.status_code in (401, 403, 429):
                return FetchResult(
                    source_name=self.name,
                    address=address,
                    facts={},
                    error=f"Movoto blocked request ({r.status_code}). "
                          "Try again later or upgrade to playwright-stealth.",
                )
            r.raise_for_status()
        except httpx.HTTPError as e:
            return FetchResult(
                source_name=self.name,
                address=address,
                facts={},
                error=f"Movoto fetch failed: {e}",
            )

        html = r.text
        # Save raw HTML for downstream LLM extraction
        self.raw_dir.mkdir(parents=True, exist_ok=True)
        raw_path = self.raw_dir / f"{address.slug}.movoto.html"
        raw_path.write_text(html)

        # Heuristic extraction of high-confidence fields. Anything more
        # subjective is left for the LLM layer reading the raw HTML.
        list_price = _to_int(
            _extract_first_match(r'"price"\s*:\s*"?\$?([\d,]+)"?', html)
            or _extract_first_match(r'\$([\d,]{6,})\s*(?:</|<span)', html)
        )
        beds = _to_int(_extract_first_match(r'(\d+)\s*(?:bed|bd)\b', html))
        baths_total = _to_float(_extract_first_match(r'(\d+(?:\.\d+)?)\s*(?:bath|ba)\b', html))
        sqft = _to_int(_extract_first_match(r'([\d,]{3,7})\s*sq(?:uare)?\s*ft', html))
        year_built = _to_int(_extract_first_match(r'[Bb]uilt\s+in\s+(\d{4})', html))

        # Lot size: residential lots are almost always <10 acres. The naive
        # `([\d.]+) acres?` regex hits "1,800 acres" in nature-preserve
        # boilerplate. Restrict to a leading 0 (e.g. 0.32) or a single-digit
        # whole/decimal (e.g. 5.5). Anything else is left for the LLM layer.
        lot_size_acres = _to_float(_extract_first_match(
            r'\b(0\.\d+|[1-9]\.\d+|[1-9])\s*acres?\b', html
        ))

        facts: dict[str, Fact] = {
            "movoto_url": Fact(value=listing_url, source=self.name, raw_ref=listing_url),
            "movoto_raw_html": Fact(value=str(raw_path), source=self.name, raw_ref=listing_url),
        }
        for k, v in [
            ("list_price", list_price),
            ("beds", beds),
            ("baths_total", baths_total),
            ("sqft", sqft),
            ("year_built", year_built),
            ("lot_size_acres", lot_size_acres),
        ]:
            if v is not None:
                facts[k] = Fact(
                    value=v, source=self.name, raw_ref=listing_url,
                    confidence="medium",
                    note="regex-extracted; verify against LLM extraction of raw HTML",
                )

        return FetchResult(
            source_name=self.name,
            address=address,
            facts=facts,
            raw={"url": listing_url, "html_path": str(raw_path), "html_bytes": len(html)},
        )

    def _find_listing_url(self, address: Address) -> str | None:
        """Search Movoto for the address and pluck the first /<city-st>/...
        listing URL out of the results page."""
        q = quote_plus(address.matched)
        try:
            r = httpx.get(
                MOVOTO_SEARCH.format(q=q),
                headers=BROWSER_HEADERS,
                timeout=30.0,
                follow_redirects=True,
            )
        except httpx.HTTPError:
            return None
        if r.status_code != 200:
            return None

        # Direct redirect path (Movoto sometimes 302s straight to the listing)
        if "/homedetails/" in str(r.url) or re.search(r"/[a-z\-]+-tx/[\d\w\-]+-tx-\d{5}", str(r.url)):
            return str(r.url)

        # Otherwise look for the first listing-shaped link in the page
        m = re.search(
            r'href="(https?://www\.movoto\.com/[a-z\-]+-[a-z]{2}/[^"]+_\d+/)"',
            r.text,
        )
        if m:
            return m.group(1)

        m = re.search(
            r'href="(/[a-z\-]+-[a-z]{2}/[^"]+_\d+/)"',
            r.text,
        )
        if m:
            return f"https://www.movoto.com{m.group(1)}"

        return None
