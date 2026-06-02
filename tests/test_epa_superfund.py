"""Logic tests for the EPA Superfund fetcher (no network)."""
import unittest

from pipeline.fetch.epa_superfund import (
    EpaSuperfundSource,
    dedupe_sites,
    summarize,
)


class TestDedupe(unittest.TestCase):
    def test_dedupes_by_registry_id(self):
        rows = [
            {"registry_id": "110013797141", "primary_name": "4 AY TRUCKING"},
            {"registry_id": "110013797141", "primary_name": "4 AY TRUCKING"},
            {"registry_id": "110000000002", "primary_name": "TERRELL NIKE"},
        ]
        sites = dedupe_sites(rows)
        self.assertEqual(len(sites), 2)
        self.assertEqual(sites[0]["name"], "4 AY TRUCKING")

    def test_falls_back_to_pgm_sys_id(self):
        rows = [
            {"pgm_sys_id": "TX0000605401", "primary_name": "SITE A"},
            {"pgm_sys_id": "TX0000605401", "primary_name": "SITE A"},
        ]
        self.assertEqual(len(dedupe_sites(rows)), 1)

    def test_skips_blank_names(self):
        rows = [
            {"registry_id": "1", "primary_name": ""},
            {"registry_id": "2", "primary_name": None},
            {"registry_id": "3", "primary_name": "REAL SITE"},
        ]
        sites = dedupe_sites(rows)
        self.assertEqual(len(sites), 1)
        self.assertEqual(sites[0]["name"], "REAL SITE")

    def test_dedupes_by_name_when_no_id(self):
        rows = [
            {"primary_name": "Acme Dump"},
            {"primary_name": "ACME DUMP"},
        ]
        self.assertEqual(len(dedupe_sites(rows)), 1)


class TestSummarize(unittest.TestCase):
    def test_empty(self):
        self.assertEqual(summarize([]), {"count": 0, "names": []})

    def test_counts_and_caps(self):
        rows = [{"registry_id": str(i), "primary_name": f"Site {i}"} for i in range(20)]
        s = summarize(rows, cap=12)
        self.assertEqual(s["count"], 20)
        self.assertEqual(len(s["names"]), 12)


class TestUrl(unittest.TestCase):
    def test_url_encodes_county_and_uppercases(self):
        url = EpaSuperfundSource()._url("TX", "El Paso")
        self.assertIn("/state_code/TX/", url)
        self.assertIn("county_name/EL%20PASO/", url)
        self.assertIn("pgm_sys_acrnm/SEMS", url)


if __name__ == "__main__":
    unittest.main()
