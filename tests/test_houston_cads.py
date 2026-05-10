"""Houston-metro CAD adapter registration + TX defaults tests."""
import unittest

from pipeline.common.address import Address
from pipeline.fetch.county import get_cad_source, supported_counties
from pipeline.fetch.county._tx_base import TxParcelCAD
from pipeline.fetch.county.tx_brazoria import BrazoriaTxCAD
from pipeline.fetch.county.tx_fortbend import FortBendTxCAD
from pipeline.fetch.county.tx_galveston import GalvestonTxCAD
from pipeline.fetch.county.tx_harris import HarrisTxCAD
from pipeline.fetch.county.tx_montgomery import MontgomeryTxCAD


HOUSTON_METRO = {
    "48201": HarrisTxCAD,
    "48157": FortBendTxCAD,
    "48339": MontgomeryTxCAD,
    "48039": BrazoriaTxCAD,
    "48167": GalvestonTxCAD,
}


def _addr_for(county_fips: str) -> Address:
    return Address(
        raw="x", matched="x", lat=29.76, lon=-95.37,
        state_fips=county_fips[:2], county_fips=county_fips[2:],
        tract_fips="000000", block_fips="0000",
        state_abbr="TX", county_name="X", zip="77001",
    )


class TestHoustonRegistry(unittest.TestCase):
    def test_all_five_registered(self):
        for fips in HOUSTON_METRO:
            self.assertIn(fips, supported_counties(), f"{fips} not registered")

    def test_get_cad_source_returns_correct_class(self):
        for fips, cls in HOUSTON_METRO.items():
            adapter = get_cad_source(_addr_for(fips))
            self.assertIsInstance(adapter, cls, f"{fips} resolved to wrong class")

    def test_all_inherit_tx_defaults(self):
        # Harris has no public REST endpoint identified yet — its
        # service_url is intentionally empty. The other invariants
        # (TX inheritance, non-disclosure flag, valid FIPS) still hold.
        for cls in HOUSTON_METRO.values():
            self.assertTrue(issubclass(cls, TxParcelCAD))
            self.assertFalse(cls.sale_price_disclosed)
            self.assertEqual(len(cls.full_county_fips), 5)

    def test_each_has_unique_name(self):
        names = [cls.name for cls in HOUSTON_METRO.values()]
        self.assertEqual(len(names), len(set(names)))


if __name__ == "__main__":
    unittest.main()
