import unittest

from app import Inputs, annual_cp_revenue, calculate


def base(**changes):
    values = dict(capacity_mw=1, cp_price=14, effective_capacity_ratio=0.052, rpcf=1,
                  imbp_total=0, other_revenue=0, owner_share=0.5,
                  channel_enabled=False, channel_fee_rate=0.2,
                  rtu_required=True, new_meter_required=True,
                  rtu_cost=1_500_000, new_meter_cost=1_500_000)
    values.update(changes)
    return Inputs(**values)


class CalculatorTests(unittest.TestCase):
    def test_cp_uses_24_hour_effective_capacity_formula(self):
        self.assertAlmostEqual(annual_cp_revenue(1, 14, 0.052, 1), 6_377_280)

    def test_fifty_fifty_happens_after_imbp(self):
        r = calculate(base(imbp_total=377_280))
        self.assertAlmostEqual(r["배분대상 순수익"], 6_000_000)
        self.assertAlmostEqual(r["발전사업주 배분액"], 3_000_000)
        self.assertAlmostEqual(r["브이젠 배분액"], 3_000_000)

    def test_channel_fee_is_twenty_percent_of_vgen_share(self):
        r = calculate(base(imbp_total=377_280, channel_enabled=True))
        self.assertAlmostEqual(r["영업채널 수수료"], 600_000)
        self.assertAlmostEqual(r["브이젠 최종수익"], 2_400_000)

    def test_owner_pays_rtu_and_meter(self):
        r = calculate(base(imbp_total=377_280))
        self.assertAlmostEqual(r["발전사업주 RTU·신자취 부담"], 3_000_000)
        self.assertAlmostEqual(r["발전사업주 1년차 실수익"], 0)


if __name__ == "__main__":
    unittest.main()
