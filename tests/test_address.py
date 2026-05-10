"""Tests for address parsing/slug logic that don't hit the network."""
import unittest

from pipeline.common.address import Address


class TestAddressSlug(unittest.TestCase):
    def _addr(self, matched: str) -> Address:
        return Address(
            raw=matched, matched=matched,
            lat=0.0, lon=0.0,
            state_fips="48", county_fips="339",
            tract_fips="691301", block_fips="0000",
            state_abbr="TX", county_name="Montgomery", zip="77381",
        )

    def test_slug_basic(self):
        a = self._addr("31 Glenleigh Pl, Spring, TX, 77381")
        self.assertEqual(a.slug, "31-glenleigh-pl-spring-tx-77381")

    def test_slug_strips_punctuation(self):
        a = self._addr("123 O'Brien Ct., Apt #4, Austin, TX, 78701")
        self.assertNotIn("'", a.slug)
        self.assertNotIn(".", a.slug)
        self.assertNotIn("#", a.slug)

    def test_full_fips_codes(self):
        a = self._addr("31 Glenleigh Pl, Spring, TX, 77381")
        self.assertEqual(a.full_county_fips, "48339")
        self.assertEqual(a.full_tract_fips, "48339691301")


if __name__ == "__main__":
    unittest.main()
