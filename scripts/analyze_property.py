#!/usr/bin/env python3
"""
Best-effort property data extraction.

This is a *fallback* helper — Claude Code's WebFetch is the primary path.
This script gives quick structured JSON when you want to short-circuit the
LLM-based extraction.

Usage:
    python3 analyze_property.py "1234 Oak St, Austin, TX 78701"
    python3 analyze_property.py "https://www.zillow.com/homedetails/..."

Note: Zillow/Redfin actively block scrapers. Expect frequent failures and
fall back to manual entry / WebFetch via Claude.
"""
import json
import re
import sys
import urllib.parse
import urllib.request
from pathlib import Path

UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"
)


def fetch(url: str, timeout: int = 15) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept-Language": "en-US,en;q=0.9"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read().decode("utf-8", errors="ignore")


def extract_facts(html: str) -> dict:
    """Pull common fields from a typical listing page via regex.

    Brittle by design — assumes the site renders facts as visible text or
    JSON-LD. If a field isn't found, it stays None.
    """
    facts = {
        "list_price": None,
        "beds": None,
        "baths": None,
        "sqft": None,
        "lot_size": None,
        "year_built": None,
        "property_type": None,
        "hoa_monthly": None,
        "tax_annual": None,
        "address": None,
    }

    # JSON-LD Product/Residence blocks (used by Zillow, Redfin, Realtor)
    for m in re.finditer(r'<script[^>]*type="application/ld\+json"[^>]*>(.*?)</script>',
                         html, re.S):
        try:
            data = json.loads(m.group(1))
            if isinstance(data, list):
                for item in data:
                    _absorb_jsonld(item, facts)
            else:
                _absorb_jsonld(data, facts)
        except json.JSONDecodeError:
            continue

    # Plain-text fallback patterns
    if facts["list_price"] is None:
        m = re.search(r'\$([\d,]{6,12})(?!\s*(?:lot|sq))', html)
        if m:
            facts["list_price"] = int(m.group(1).replace(",", ""))

    if facts["beds"] is None:
        m = re.search(r'(\d+)\s*(?:bd|bed|bedroom)', html, re.I)
        if m:
            facts["beds"] = int(m.group(1))

    if facts["baths"] is None:
        m = re.search(r'(\d+(?:\.\d)?)\s*(?:ba|bath|bathroom)', html, re.I)
        if m:
            facts["baths"] = float(m.group(1))

    if facts["sqft"] is None:
        m = re.search(r'([\d,]+)\s*(?:sq\.?\s?ft|sqft|square feet)', html, re.I)
        if m:
            facts["sqft"] = int(m.group(1).replace(",", ""))

    if facts["year_built"] is None:
        m = re.search(r'built[^0-9]{0,10}(19|20)\d{2}', html, re.I)
        if m:
            facts["year_built"] = int(m.group(0)[-4:])

    return facts


def _absorb_jsonld(item: dict, facts: dict):
    if not isinstance(item, dict):
        return
    t = item.get("@type", "")
    if isinstance(t, list):
        t = " ".join(t)
    t = str(t).lower()

    if "residence" in t or "house" in t or "apartment" in t or "product" in t:
        if facts["address"] is None:
            addr = item.get("address")
            if isinstance(addr, dict):
                parts = [addr.get("streetAddress"), addr.get("addressLocality"),
                         f"{addr.get('addressRegion','')} {addr.get('postalCode','')}".strip()]
                facts["address"] = ", ".join(p for p in parts if p)
        if facts["beds"] is None and "numberOfRooms" in item:
            try:
                facts["beds"] = int(item["numberOfRooms"])
            except (TypeError, ValueError):
                pass
        if facts["sqft"] is None and "floorSize" in item:
            fs = item["floorSize"]
            if isinstance(fs, dict) and "value" in fs:
                try:
                    facts["sqft"] = int(float(fs["value"]))
                except (TypeError, ValueError):
                    pass
        if facts["list_price"] is None and "offers" in item:
            offers = item["offers"]
            if isinstance(offers, dict):
                price = offers.get("price")
                if price:
                    try:
                        facts["list_price"] = int(float(price))
                    except (TypeError, ValueError):
                        pass


def main():
    if len(sys.argv) < 2:
        print("Usage: analyze_property.py <address-or-url>", file=sys.stderr)
        sys.exit(1)

    arg = sys.argv[1]
    if arg.startswith("http"):
        url = arg
        address = None
    else:
        # Build a Zillow search URL — best-effort
        q = urllib.parse.quote(arg)
        url = f"https://www.zillow.com/homes/{q}_rb/"
        address = arg

    facts = {"source_url": url, "input_address": address}
    try:
        html = fetch(url)
        facts.update(extract_facts(html))
        facts["fetch_status"] = "ok"
    except Exception as e:
        facts["fetch_status"] = f"failed: {e}"

    Path("property_facts.json").write_text(json.dumps(facts, indent=2))
    json.dump(facts, sys.stdout, indent=2)
    print()


if __name__ == "__main__":
    main()
