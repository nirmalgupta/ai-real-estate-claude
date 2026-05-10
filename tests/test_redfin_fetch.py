"""Pure-logic tests for the Redfin per-property fetcher (no network)."""
import json
import unittest

from pipeline.fetch.redfin import _find_listing_block, _to_float, _to_int


SAMPLE_BLOCK = {
    "@context": "https://schema.org",
    "@type": ["Product", "RealEstateListing"],
    "name": "5646 Highflyer Hills Trl",
    "description": "Discover the perfect blend...",
    "url": "https://www.redfin.com/TX/Frisco/5646-Highflyer-Hills-Trl-75036/home/104485204",
    "datePosted": "2026-04-30T20:09:49.247Z",
    "offers": {
        "@type": "Offer",
        "price": "1049000",
        "priceCurrency": "USD",
    },
    "mainEntity": {
        "@type": "SingleFamilyResidence",
        "numberOfBedrooms": "5",
        "numberOfBathroomsTotal": "5",
        "yearBuilt": "2016",
        "accommodationCategory": "Single Family Residential",
        "floorSize": {"value": "4005", "unitText": "FTK"},
    },
    "image": [{"url": f"x{i}"} for i in range(40)],
}


def _wrap_html(blocks: list[dict]) -> str:
    parts = [
        '<html><head>',
        '<script type="application/ld+json">{"@context":"http://schema.org","@type":"Organization","name":"Redfin"}</script>',
    ]
    for b in blocks:
        parts.append(f'<script type="application/ld+json">{json.dumps(b)}</script>')
    parts.append('</head><body></body></html>')
    return "".join(parts)


class TestFindBlock(unittest.TestCase):
    def test_finds_real_estate_listing(self):
        html = _wrap_html([SAMPLE_BLOCK])
        block = _find_listing_block(html)
        self.assertIsNotNone(block)
        self.assertEqual(block["mainEntity"]["yearBuilt"], "2016")

    def test_handles_type_as_string(self):
        b = dict(SAMPLE_BLOCK)
        b["@type"] = "RealEstateListing"
        block = _find_listing_block(_wrap_html([b]))
        self.assertIsNotNone(block)

    def test_skips_unrelated_ld_json(self):
        html = _wrap_html([])  # only the Organization block
        self.assertIsNone(_find_listing_block(html))

    def test_returns_none_when_no_ld_json(self):
        self.assertIsNone(_find_listing_block("<html></html>"))


class TestCoercers(unittest.TestCase):
    def test_int(self):
        self.assertEqual(_to_int("1,049,000"), 1049000)
        self.assertEqual(_to_int("5"), 5)
        self.assertIsNone(_to_int(""))
        self.assertIsNone(_to_int(None))
        self.assertIsNone(_to_int("abc"))

    def test_float(self):
        self.assertEqual(_to_float("5.0"), 5.0)
        self.assertEqual(_to_float("4,005"), 4005.0)
        self.assertIsNone(_to_float(None))


if __name__ == "__main__":
    unittest.main()
