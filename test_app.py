import unittest

from app import Inputs, annual_cp_revenue, calculate


def base(**changes):
    values = dict(capacity_mw=1, cp_price=14, effective_capacity_ratio=0.1278, rpcf=1.0,
                  mwp_per_mw=500_000, map_per_mw=500_000, imbp_per_mw=800_000,
                  base_revenue_per_mw=100_000_000, owner_share=0.5,
                  channel_enabled=False, channel_fee_rate=0.2,
                  rtu_required=True, new_meter_required=True,
                  rtu_cost=1_500_000, new_meter_cost=1_500_000)
    values.update(changes)
    return Inputs(**values)


class CalculatorTests(unittest.TestCase):
    def test_land_solar_cp_formula(self):
        self.assertAlmostEqual(annual_cp_revenue(1, 14, 0.1278, 1.0), 15_673_392)

    def test_base_revenue_is_not_distributed(self):
        r = calculate(base())
        self.assertEqual(r["기본 전력·REC 수익"], 100_000_000)
        self.assertAlmostEqual(r["배분대상 순수익"], 15_873_392)
        self.assertAlmostEqual(r["발전사업주 배분액"], 7_936_696)

    def test_fifty_fifty_after_imbp(self):
        r = calculate(base())
        self.assertAlmostEqual(r["발전사업주 배분액"], r["브이젠 배분액"])

    def test_channel_fee_is_twenty_percent_of_vgen_share(self):
        r = calculate(base(channel_enabled=True))
        self.assertAlmostEqual(r["영업채널 수수료"], r["브이젠 배분액"] * 0.2)
        self.assertAlmostEqual(r["브이젠 최종수익"], r["브이젠 배분액"] * 0.8)

    def test_owner_pays_fixed_site_infrastructure(self):
        r = calculate(base())
        self.assertEqual(r["발전사업주 RTU·신자취 부담"], 3_000_000)
        self.assertAlmostEqual(r["발전사업주 1년차 추가수익"], r["발전사업주 배분액"] - 3_000_000)


if __name__ == "__main__":
    unittest.main()
