"""Miami-metro (FL) CAD adapter registration + disclosure-state tests."""
import unittest

from pipeline.common.address import Address
from pipeline.fetch.county import get_cad_source, supported_counties
from pipeline.fetch.county._fl_base import FlParcelCAD
from pipeline.fetch.county.fl_broward import BrowardFlCAD
from pipeline.fetch.county.fl_miami_dade import MiamiDadeFlCAD
from pipeline.fetch.county.fl_palmbeach import PalmBeachFlCAD


MIAMI_METRO = {
    "12086": MiamiDadeFlCAD,
    "12011": BrowardFlCAD,
    "12099": PalmBeachFlCAD,
}


def _addr_for(county_fips: str) -> Address:
    return Address(
        raw="x", matched="x", lat=25.76, lon=-80.19,
        state_fips=county_fips[:2], county_fips=county_fips[2:],
        tract_fips="000000", block_fips="0000",
        state_abbr="FL", county_name="X", zip="33101",
    )


class TestMiamiRegistry(unittest.TestCase):
    def test_registered(self):
        for fips in MIAMI_METRO:
            self.assertIn(fips, supported_counties())

    def test_resolution(self):
        for fips, cls in MIAMI_METRO.items():
            self.assertIsInstance(get_cad_source(_addr_for(fips)), cls)

    def test_fl_disclosure(self):
        # Florida discloses sale prices — opposite of TX. The flag is
        # what controls whether the base class will surface sale-price
        # facts; per-county attr_maps may legitimately omit sale fields
        # if that specific county's public layer doesn't publish them
        # (Miami-Dade exposes sale history through a separate service).
        for cls in MIAMI_METRO.values():
            self.assertTrue(issubclass(cls, FlParcelCAD))
            self.assertTrue(cls.sale_price_disclosed,
                            f"{cls.__name__} should expose sale price (FL)")


if __name__ == "__main__":
    unittest.main()
