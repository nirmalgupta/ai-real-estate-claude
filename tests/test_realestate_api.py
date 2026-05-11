"""Logic tests for RealEstateAPI fallback (no network)."""
import unittest

from pipeline.fetch.realestate_api import _pick, _walk


class WalkTests(unittest.TestCase):
    def test_dotted_path(self):
        obj = {"a": {"b": {"c": 42}}}
        self.assertEqual(_walk(obj, "a.b.c"), 42)

    def test_missing_part(self):
        obj = {"a": {"b": {}}}
        self.assertIsNone(_walk(obj, "a.b.c"))

    def test_flat_key(self):
        self.assertEqual(_walk({"flat": 1}, "flat"), 1)

    def test_non_dict_intermediate(self):
        self.assertIsNone(_walk({"a": "string"}, "a.b"))


class PickTests(unittest.TestCase):
    def test_first_match_wins(self):
        obj = {"assessor": {"totalValue": 500_000},
               "assessedValue": 600_000}
        # We list assessment.totalValue then assessor.totalValue;
        # assessor wins because assessment is absent.
        self.assertEqual(
            _pick(obj, ("assessment.totalValue", "assessor.totalValue",
                         "assessedValue")),
            500_000,
        )

    def test_skips_empties(self):
        obj = {"a": "", "b": [], "c": None, "d": 7}
        self.assertEqual(_pick(obj, ("a", "b", "c", "d")), 7)

    def test_no_match_returns_none(self):
        self.assertIsNone(_pick({}, ("foo", "bar")))


if __name__ == "__main__":
    unittest.main()
