import unittest

from app import Inputs, allocate_revenue, settle_market


def params(**changes):
    base = dict(
        capacity_mw=1, daily_generation_hours=3.6, degradation_pct=0.005, years=20,
        existing_smp=120, rec_price=60, da_smp=120, rt_smp=120,
        da_plan_ratio=1, rt_plan_ratio=1, actual_ratio=1, available_ratio=1,
        rpcf=1, efcr=0.1278, cp_price=10, map_price=0, mwp_price=0,
        imb_tolerance=0.08, imb_factor=1, contract="50:50 순수익 배분",
        owner_share=0.5, sales_fee_rate=0.2, rtu_cost=1_500_000,
        meter_cost=1_500_000, annual_service_cost=0,
    )
    base.update(changes)
    return Inputs(**base)


class CalculatorTests(unittest.TestCase):
    def test_efcr_applies_to_cp_quantity(self):
        result = settle_market(1_000, params())
        self.assertAlmostEqual(result["CP 인정물량"], 127.8)
        self.assertAlmostEqual(result["CP"], 1_278)

    def test_fifty_fifty_splits_after_imb_and_fee_uses_vgen_net(self):
        settlement = {"CP": 100, "MEP": 40, "MAP": 10, "MWP": 0, "IMB": -50, "VPP 순추가수익": 100}
        result = allocate_revenue(settlement, params())
        self.assertEqual(result["사업주 VPP 수익"], 50)
        self.assertEqual(result["브이젠 수수료 전 수익"], 50)
        self.assertEqual(result["영업수수료"], 10)
        self.assertEqual(result["브이젠 수수료 후 수익"], 40)

    def test_standard_fee_is_not_based_on_cp_gross(self):
        settlement = {"CP": 100, "MEP": 40, "MAP": 10, "MWP": 0, "IMB": -50, "VPP 순추가수익": 100}
        result = allocate_revenue(settlement, params(contract="기본 배분"))
        self.assertEqual(result["영업수수료"], 10)


if __name__ == "__main__":
    unittest.main()
