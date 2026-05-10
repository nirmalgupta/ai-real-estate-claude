"""Austin-metro CAD adapter registration tests."""
import unittest

from pipeline.common.address import Address
from pipeline.fetch.county import get_cad_source, supported_counties
from pipeline.fetch.county._tx_base import TxParcelCAD
from pipeline.fetch.county.tx_hays import HaysTxCAD
from pipeline.fetch.county.tx_travis import TravisTxCAD
from pipeline.fetch.county.tx_williamson import WilliamsonTxCAD


AUSTIN_METRO = {
    "48453": TravisTxCAD,
    "48491": WilliamsonTxCAD,
    "48209": HaysTxCAD,
}


def _addr_for(county_fips: str) -> Address:
    return Address(
        raw="x", matched="x", lat=30.27, lon=-97.74,
        state_fips=county_fips[:2], county_fips=county_fips[2:],
        tract_fips="000000", block_fips="0000",
        state_abbr="TX", county_name="X", zip="78701",
    )


class TestAustinRegistry(unittest.TestCase):
    def test_registered(self):
        for fips in AUSTIN_METRO:
            self.assertIn(fips, supported_counties())

    def test_resolution(self):
        for fips, cls in AUSTIN_METRO.items():
            self.assertIsInstance(get_cad_source(_addr_for(fips)), cls)

    def test_tx_invariants(self):
        for cls in AUSTIN_METRO.values():
            self.assertTrue(issubclass(cls, TxParcelCAD))
            self.assertFalse(cls.sale_price_disclosed)
            self.assertTrue(cls.service_url)


if __name__ == "__main__":
    unittest.main()
