"""Pure-logic tests for OSM amenities helpers (no network)."""
import unittest

from pipeline.fetch.osm_amenities import (
    _build_query,
    _classify_element,
    _element_latlon,
    _haversine_miles,
)


class TestHaversine(unittest.TestCase):
    def test_zero(self):
        self.assertAlmostEqual(_haversine_miles(0, 0, 0, 0), 0.0, places=6)

    def test_one_degree_lat(self):
        self.assertAlmostEqual(_haversine_miles(0, 0, 1, 0), 69.09, delta=0.5)


class TestClassify(unittest.TestCase):
    def test_supermarket(self):
        self.assertEqual(_classify_element({"shop": "supermarket"}),
                         "nearest_supermarkets")

    def test_convenience(self):
        self.assertEqual(_classify_element({"shop": "convenience"}),
                         "nearest_convenience_stores")

    def test_pharmacy(self):
        self.assertEqual(_classify_element({"amenity": "pharmacy"}),
                         "nearest_pharmacies")

    def test_restaurant(self):
        self.assertEqual(_classify_element({"amenity": "restaurant"}),
                         "nearest_restaurants")

    def test_unrelated_tag_returns_none(self):
        self.assertIsNone(_classify_element({"highway": "primary"}))
        self.assertIsNone(_classify_element({}))


class TestElementLatLon(unittest.TestCase):
    def test_node_direct(self):
        self.assertEqual(_element_latlon({"lat": 1.0, "lon": 2.0}), (1.0, 2.0))

    def test_way_with_center(self):
        e = {"type": "way", "center": {"lat": 1.0, "lon": 2.0}}
        self.assertEqual(_element_latlon(e), (1.0, 2.0))

    def test_missing_returns_none(self):
        self.assertIsNone(_element_latlon({"type": "way"}))


class TestBuildQuery(unittest.TestCase):
    def test_all_kinds_present(self):
        q = _build_query(33.0, -96.9)
        self.assertIn("shop", q)
        self.assertIn("supermarket", q)
        self.assertIn("convenience", q)
        self.assertIn("pharmacy", q)
        self.assertIn("restaurant", q)
        self.assertIn("around:", q)
        self.assertIn("33.0", q)
        self.assertIn("-96.9", q)


if __name__ == "__main__":
    unittest.main()
