"""Raleigh-metro (NC) CAD adapter registration + disclosure tests."""
import unittest

from pipeline.common.address import Address
from pipeline.fetch.county import get_cad_source, supported_counties
from pipeline.fetch.county._nc_base import NcParcelCAD
from pipeline.fetch.county.nc_chatham import ChathamNcCAD
from pipeline.fetch.county.nc_durham import DurhamNcCAD
from pipeline.fetch.county.nc_johnston import JohnstonNcCAD
from pipeline.fetch.county.nc_orange import OrangeNcCAD
from pipeline.fetch.county.nc_wake import WakeNcCAD


RALEIGH_METRO = {
    "37183": WakeNcCAD,
    "37063": DurhamNcCAD,
    "37135": OrangeNcCAD,
    "37037": ChathamNcCAD,
    "37101": JohnstonNcCAD,
}


def _addr_for(county_fips: str) -> Address:
    return Address(
        raw="x", matched="x", lat=35.78, lon=-78.64,
        state_fips=county_fips[:2], county_fips=county_fips[2:],
        tract_fips="000000", block_fips="0000",
        state_abbr="NC", county_name="X", zip="27601",
    )


class TestRaleighRegistry(unittest.TestCase):
    def test_registered(self):
        for fips in RALEIGH_METRO:
            self.assertIn(fips, supported_counties())

    def test_resolution(self):
        for fips, cls in RALEIGH_METRO.items():
            self.assertIsInstance(get_cad_source(_addr_for(fips)), cls)

    def test_nc_disclosure(self):
        for cls in RALEIGH_METRO.values():
            self.assertTrue(issubclass(cls, NcParcelCAD))
            self.assertTrue(cls.sale_price_disclosed)
            self.assertIn("last_sale_price", cls.attr_map)
            self.assertIn("last_sale_date", cls.attr_map)


if __name__ == "__main__":
    unittest.main()
