import unittest

from app import Inputs, calculate


def base(**changes):
    values = dict(
        capacity_mw=1, cp_factor=1, rpcf=1, extra_revenue_per_mw=14_000_000,
        imbp_per_mw=1_000_000, owner_share=0.5, channel_enabled=False,
        channel_fee_rate=0.2, rtu_required=True, new_meter_required=True,
        rtu_cost=1_500_000, new_meter_cost=1_500_000,
    )
    values.update(changes)
    return Inputs(**values)


class CalculatorTests(unittest.TestCase):
    def test_default_contract_matches_business_case(self):
        r = calculate(base())
        self.assertEqual(r["총 VPP 추가수익"], 14_000_000)
        self.assertEqual(r["배분대상 순수익"], 13_000_000)
        self.assertEqual(r["발전사업주 배분액"], 6_500_000)
        self.assertEqual(r["브이젠 배분액"], 6_500_000)

    def test_channel_fee_is_twenty_percent_of_vgen_share(self):
        r = calculate(base(channel_enabled=True))
        self.assertEqual(r["영업채널 수수료"], 1_300_000)
        self.assertEqual(r["브이젠 최종수익"], 5_200_000)

    def test_owner_pays_rtu_and_meter(self):
        r = calculate(base())
        self.assertEqual(r["발전사업주 RTU·신자취 부담"], 3_000_000)
        self.assertEqual(r["발전사업주 1년차 실수익"], 3_500_000)

    def test_cp_and_rpcf_scale_gross_revenue(self):
        r = calculate(base(cp_factor=0.8, rpcf=0.75))
        self.assertEqual(r["총 VPP 추가수익"], 8_400_000)


if __name__ == "__main__":
    unittest.main()
