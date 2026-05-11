"""Logic tests for Redfin sold-comp finder (no network)."""
import unittest
from datetime import datetime, timezone

from pipeline.fetch.redfin_comps import (
    _haversine_miles,
    _parse_sold_date,
    _passes_filter,
    _similarity_score,
    _to_comp_dict,
)
from pipeline.search.redfin import Listing


def _listing(**kw) -> Listing:
    defaults = dict(
        address="111 Comp Ct", city="Frisco", state="TX", zip="75036",
        price=850000, beds=4, baths=3.0, sqft=2800, lot_sqft=7500,
        year_built=2018, days_on_market=None, price_per_sqft=303,
        hoa_monthly=None, status="Sold", property_type="Single Family Residential",
        mls_number="20012345", url="https://www.redfin.com/x", lat=33.15,
        lon=-96.81, sold_date="Jan 15, 2026",
    )
    defaults.update(kw)
    return Listing(**defaults)


class TestParseSoldDate(unittest.TestCase):
    def test_known_formats(self):
        self.assertIsNotNone(_parse_sold_date("Jan 15, 2026"))
        self.assertIsNotNone(_parse_sold_date("2026-01-15"))
        self.assertIsNotNone(_parse_sold_date("01/15/2026"))

    def test_garbage(self):
        self.assertIsNone(_parse_sold_date("yesterday"))
        self.assertIsNone(_parse_sold_date(None))
        self.assertIsNone(_parse_sold_date(""))


class TestPassesFilter(unittest.TestCase):
    def setUp(self):
        self.subject = dict(
            subject_lat=33.15, subject_lon=-96.82,
            subject_sqft=3000, subject_beds=4,
            subject_type="Single Family Residential",
            radius_miles=1.0, sqft_band=0.30, bed_band=1,
            cutoff=datetime(2025, 5, 11, tzinfo=timezone.utc),
        )

    def test_passes_close_similar(self):
        L = _listing(sqft=2900, beds=4, lat=33.155, lon=-96.815)
        self.assertTrue(_passes_filter(L, **self.subject))

    def test_fails_no_price(self):
        L = _listing(price=None)
        self.assertFalse(_passes_filter(L, **self.subject))

    def test_fails_too_far(self):
        L = _listing(lat=34.0, lon=-95.0)
        self.assertFalse(_passes_filter(L, **self.subject))

    def test_fails_too_old(self):
        L = _listing(sold_date="Jan 15, 2024")
        self.assertFalse(_passes_filter(L, **self.subject))

    def test_fails_sqft_band(self):
        # 3000 ±30% = 2100..3900. 1500 is too small.
        L = _listing(sqft=1500)
        self.assertFalse(_passes_filter(L, **self.subject))

    def test_fails_bed_band(self):
        L = _listing(beds=1)
        self.assertFalse(_passes_filter(L, **self.subject))

    def test_passes_when_property_type_blank(self):
        # Missing property_type on comp shouldn't block the match
        s = dict(self.subject)
        s["subject_type"] = None
        L = _listing()
        self.assertTrue(_passes_filter(L, **s))


class TestSimilarityScore(unittest.TestCase):
    def test_closer_better(self):
        cutoff = datetime(2025, 5, 11, tzinfo=timezone.utc)
        near = _similarity_score(_listing(lat=33.151, lon=-96.821),
                                 3000, 33.150, -96.820, cutoff)
        far = _similarity_score(_listing(lat=33.20, lon=-96.85),
                                3000, 33.150, -96.820, cutoff)
        self.assertLess(near, far)

    def test_size_match_better(self):
        cutoff = datetime(2025, 5, 11, tzinfo=timezone.utc)
        match = _similarity_score(_listing(sqft=3000),
                                  3000, 33.15, -96.82, cutoff)
        mismatch = _similarity_score(_listing(sqft=4500),
                                     3000, 33.15, -96.82, cutoff)
        self.assertLess(match, mismatch)


class TestToCompDict(unittest.TestCase):
    def test_distance_computed(self):
        L = _listing(lat=33.155, lon=-96.815)
        d = _to_comp_dict(L, subject_lat=33.150, subject_lon=-96.820)
        self.assertIsNotNone(d["distance_miles"])
        self.assertLess(d["distance_miles"], 1.0)

    def test_serializes_core_fields(self):
        L = _listing()
        d = _to_comp_dict(L, 33.15, -96.82)
        for k in ("address", "sold_date", "sold_price", "price_per_sqft",
                  "beds", "baths", "sqft", "lot_sqft", "year_built",
                  "distance_miles", "url"):
            self.assertIn(k, d)


class TestHaversine(unittest.TestCase):
    def test_zero_distance(self):
        self.assertEqual(_haversine_miles(33.15, -96.82, 33.15, -96.82), 0)


if __name__ == "__main__":
    unittest.main()
