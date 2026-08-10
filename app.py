from __future__ import annotations

from dataclasses import asdict, dataclass
from io import BytesIO

import pandas as pd
import plotly.graph_objects as go
import streamlit as st


SOLAR_EFCR = 0.1278
ESS_5H_EFCR = 0.81865
DEFAULT_RTU_COST = 1_500_000
DEFAULT_NEW_METER_COST = 1_500_000


@dataclass(frozen=True)
class Inputs:
    capacity_mw: float
    daily_generation_hours: float
    degradation_pct: float
    years: int
    existing_smp: float
    rec_price: float
    da_smp: float
    rt_smp: float
    da_plan_ratio: float
    rt_plan_ratio: float
    actual_ratio: float
    available_ratio: float
    rpcf: float
    efcr: float
    cp_price: float
    map_price: float
    mwp_price: float
    imb_tolerance: float
    imb_factor: float
    contract: str
    owner_share: float
    sales_fee_rate: float
    rtu_cost: float
    meter_cost: float
    annual_service_cost: float


def annual_generation_kwh(capacity_mw: float, daily_hours: float, degradation_pct: float, year: int = 1) -> float:
    return capacity_mw * 1_000 * daily_hours * 365 * ((1 - degradation_pct) ** (year - 1))


def settle_market(gen_kwh: float, p: Inputs) -> dict[str, float]:
    """연간 등가값 기반 영업 시뮬레이션.

    KPX 실제 정산은 거래시간별 계량·입찰·급전 자료로 수행된다. 이 함수는 같은
    항목의 방향과 배분을 설명하기 위한 연간 등가 근사이며 실제 정산서 대체물이 아니다.
    """
    daos = gen_kwh * p.da_plan_ratio
    rtos = gen_kwh * p.rt_plan_ratio
    mgo = gen_kwh * p.actual_ratio
    ra = gen_kwh * p.available_ratio

    market_energy = p.da_smp * daos + p.rt_smp * (mgo - daos)
    existing_energy = p.existing_smp * mgo
    mep = market_energy - existing_energy

    capacity_recognition = min(max(p.rpcf, 0), 1) * min(max(p.efcr, 0), 1)
    cp_quantity = min(ra, rtos, mgo) * capacity_recognition
    cp = cp_quantity * p.cp_price

    map_quantity = max(daos - max(mgo, rtos), 0)
    map_payment = map_quantity * p.map_price
    mwp_quantity = max(rtos - mgo, 0)
    mwp = mwp_quantity * p.mwp_price

    imbalance_quantity = max(abs(mgo - rtos) - rtos * p.imb_tolerance, 0)
    imb = -imbalance_quantity * p.rt_smp * p.imb_factor
    net_vpp = cp + mep + map_payment + mwp + imb
    return {
        "CP": cp,
        "MEP": mep,
        "MAP": map_payment,
        "MWP": mwp,
        "IMB": imb,
        "VPP 순추가수익": net_vpp,
        "DAOS": daos,
        "RTOS": rtos,
        "MGO": mgo,
        "RA": ra,
        "CP 인정물량": cp_quantity,
        "용량인정계수(RPCF×EFCR)": capacity_recognition,
        "IMB 대상물량": imbalance_quantity,
    }


def allocate_revenue(settlement: dict[str, float], p: Inputs) -> dict[str, float]:
    if p.contract == "50:50 순수익 배분":
        owner_before_fee = settlement["VPP 순추가수익"] * p.owner_share
        vgen_before_fee = settlement["VPP 순추가수익"] * (1 - p.owner_share)
    else:
        owner_before_fee = settlement["MEP"] + settlement["MAP"] + settlement["MWP"]
        vgen_before_fee = settlement["CP"] + settlement["IMB"]

    # 영업수수료는 IMB 및 계약 배분을 반영한 브이젠 양(+)의 수익에만 적용한다.
    sales_fee = max(vgen_before_fee, 0) * p.sales_fee_rate
    vgen_after_fee = vgen_before_fee - sales_fee
    return {
        "사업주 VPP 수익": owner_before_fee,
        "브이젠 수수료 전 수익": vgen_before_fee,
        "영업수수료": sales_fee,
        "브이젠 수수료 후 수익": vgen_after_fee,
    }


def build_cashflow(p: Inputs) -> pd.DataFrame:
    rows = []
    cumulative_owner = cumulative_vgen = 0.0
    investment = p.rtu_cost + p.meter_cost
    for year in range(1, p.years + 1):
        gen = annual_generation_kwh(p.capacity_mw, p.daily_generation_hours, p.degradation_pct, year)
        settlement = settle_market(gen, p)
        allocation = allocate_revenue(settlement, p)
        vgen_capex = investment if year == 1 else 0.0
        owner_net = allocation["사업주 VPP 수익"]
        vgen_net = allocation["브이젠 수수료 후 수익"] - vgen_capex - p.annual_service_cost
        cumulative_owner += owner_net
        cumulative_vgen += vgen_net
        rows.append({
            "연차": year,
            "발전량(kWh)": gen,
            **{k: settlement[k] for k in ["CP", "MEP", "MAP", "MWP", "IMB", "VPP 순추가수익"]},
            **allocation,
            "RTU·신자취 투자비": vgen_capex,
            "연간 운영비": p.annual_service_cost,
            "사업주 순추가수익": owner_net,
            "브이젠 순수익": vgen_net,
            "사업주 누적수익": cumulative_owner,
            "브이젠 누적수익": cumulative_vgen,
        })
    return pd.DataFrame(rows)


def won(value: float) -> str:
    sign = "-" if value < 0 else ""
    return f"{sign}{abs(value) / 10_000:,.0f}만원"


def pct(value: float) -> str:
    return f"{value * 100:,.3f}%"


st.set_page_config(page_title="V-GEN VPP 수익 계산기", page_icon="⚡", layout="wide")
st.markdown(
    """
    <style>
    .block-container {padding-top: 1.3rem; max-width: 1500px}
    .hero {padding: 1.6rem 2rem; border-radius: 22px; color: white;
      background: linear-gradient(125deg,#09284a,#08667b,#14a08f); margin-bottom: 1rem}
    .hero h1 {margin:0;font-size:2rem}.hero p{margin:.5rem 0 0;opacity:.92}
    [data-testid="stMetric"] {background:white;border:1px solid #e5e7eb;padding:1rem;border-radius:16px}
    </style>
    <div class="hero"><h1>V-GEN VPP 수익 계산기</h1>
    <p>전력시장 정산 항목, 용량인정계수, 계약 배분과 구축비를 한 화면에서 조정하는 영업 시뮬레이터</p></div>
    """,
    unsafe_allow_html=True,
)

with st.sidebar:
    st.header("빠른 설정")
    region = st.selectbox("시장", ["제주 시범사업", "육지 재생에너지 입찰시장"])
    asset = st.selectbox("자원 구성", ["태양광", "태양광 + 5시간 ESS"])
    contract = st.selectbox("계약 정책", ["50:50 순수익 배분", "기본 배분"])
    default_efcr = SOLAR_EFCR if asset == "태양광" else ESS_5H_EFCR
    st.caption("모든 기본값은 아래에서 직접 수정할 수 있습니다.")

tab1, tab2, tab3, tab4 = st.tabs(["① 발전소·가격", "② 정산 파라미터", "③ 계약·투자비", "④ 계산 기준"])
with tab1:
    a, b, c = st.columns(3)
    with a:
        capacity_mw = st.number_input("설비용량(MW)", 0.01, 1000.0, 1.0, 0.1)
        daily_hours = st.number_input("일평균 발전시간", 0.1, 24.0, 3.6, 0.1)
        degradation = st.number_input("연간 열화율(%)", 0.0, 10.0, 0.5, 0.1) / 100
        years = st.slider("분석기간(년)", 1, 30, 20)
    with b:
        existing_smp = st.number_input("기존 SMP 상당단가(원/kWh)", 0.0, 1000.0, 120.0, 1.0)
        rec_price = st.number_input("REC 상당단가(원/kWh)", 0.0, 1000.0, 60.0, 1.0)
        da_smp = st.number_input("DASMP(원/kWh)", -1000.0, 2000.0, 115.0 if region == "제주 시범사업" else 120.0, 1.0)
        rt_smp = st.number_input("RTSMP(원/kWh)", -1000.0, 2000.0, 120.0 if region == "제주 시범사업" else 122.0, 1.0)
    with c:
        da_ratio = st.number_input("DAOS/기준발전량", 0.0, 2.0, 0.95, 0.01)
        rt_ratio = st.number_input("RTOS/기준발전량", 0.0, 2.0, 0.93, 0.01)
        actual_ratio = st.number_input("MGO/기준발전량", 0.0, 2.0, 1.00, 0.01)
        available_ratio = st.number_input("RA/기준발전량", 0.0, 2.0, 0.95, 0.01)

with tab2:
    a, b, c = st.columns(3)
    with a:
        rpcf = st.number_input("RPCF(%)", 0.0, 150.0, 100.0, 0.1) / 100
        efcr = st.number_input("EFCR(%)", 0.0, 150.0, default_efcr * 100, 0.001) / 100
        st.caption(f"기본값: 태양광 {SOLAR_EFCR*100:.2f}% / 5시간 ESS {ESS_5H_EFCR*100:.3f}%")
    with b:
        cp_price = st.number_input("CP 단가(원/kWh-인정량)", -1000.0, 2000.0, 22.0 if region == "제주 시범사업" else 11.0, 0.1)
        map_price = st.number_input("MAP 단가(원/kWh)", -1000.0, 2000.0, 2.5 if region == "제주 시범사업" else 0.8, 0.1)
        mwp_price = st.number_input("MWP 단가(원/kWh)", -1000.0, 2000.0, 1.0 if region == "제주 시범사업" else 0.5, 0.1)
    with c:
        imb_tolerance = st.number_input("IMB 허용오차율(%)", 0.0, 100.0, 8.0, 0.1) / 100
        imb_factor = st.number_input("IMB 페널티 계수", 0.0, 10.0, 1.0, 0.1)
        st.info("EFCR과 RPCF는 각각 수정되며 CP 인정계수에는 RPCF × EFCR로 반영됩니다.")

with tab3:
    a, b, c = st.columns(3)
    with a:
        if contract == "50:50 순수익 배분":
            owner_share = st.slider("사업주 배분율(%)", 0, 100, 50) / 100
            st.caption("CP+MEP+MAP+MWP+IMB 순액을 배분합니다.")
        else:
            owner_share = 0.0
            st.caption("MEP·MAP·MWP는 사업주, CP·IMB는 브이젠에 반영합니다.")
        sales_fee = st.number_input("영업수수료율(%)", 0.0, 100.0, 20.0, 1.0) / 100
        st.caption("계약 배분 및 IMB 반영 후 브이젠 양(+)의 수익에 적용")
    with b:
        include_rtu = st.checkbox("RTU 투자비 반영", True)
        rtu_cost = st.number_input("RTU 투자비(원)", 0, 100_000_000, DEFAULT_RTU_COST, 100_000, disabled=not include_rtu)
        include_meter = st.checkbox("신자취 투자비 반영", True)
        meter_cost = st.number_input("신자취 투자비(원)", 0, 100_000_000, DEFAULT_NEW_METER_COST, 100_000, disabled=not include_meter)
    with c:
        annual_service = st.number_input("연간 통신·운영비(원)", 0, 100_000_000, 0, 100_000)
        st.metric("브이젠 초기투자비", won((rtu_cost if include_rtu else 0) + (meter_cost if include_meter else 0)))

with tab4:
    st.markdown("""
    - 실제 KPX 정산은 거래시간별 입찰량·발전계획량·계량값·급전지시 및 적용 규칙으로 계산됩니다.
    - 이 계산기는 영업 검토를 위한 연간 등가 근사 모델이며, 입력값을 공개해 결과의 근거를 추적할 수 있게 설계했습니다.
    - CP 인정량은 `min(RA, RTOS, MGO) × RPCF × EFCR`로 근사합니다.
    - 50:50 계약은 `(CP + MEP + MAP + MWP + IMB) × 배분율`을 사용합니다.
    - 영업수수료는 IMB와 계약배분 이후 브이젠의 양(+)의 수익에만 적용합니다.
    """)

p = Inputs(
    capacity_mw, daily_hours, degradation, years, existing_smp, rec_price,
    da_smp, rt_smp, da_ratio, rt_ratio, actual_ratio, available_ratio,
    rpcf, efcr, cp_price, map_price, mwp_price, imb_tolerance, imb_factor,
    contract, owner_share, sales_fee, rtu_cost if include_rtu else 0,
    meter_cost if include_meter else 0, annual_service,
)
gen = annual_generation_kwh(capacity_mw, daily_hours, degradation)
settlement = settle_market(gen, p)
allocation = allocate_revenue(settlement, p)
cashflow = build_cashflow(p)

st.subheader("1년차 핵심 결과")
c1, c2, c3, c4, c5 = st.columns(5)
c1.metric("VPP 순추가수익", won(settlement["VPP 순추가수익"]))
c2.metric("사업주 추가수익", won(allocation["사업주 VPP 수익"]))
c3.metric("브이젠 수수료 전", won(allocation["브이젠 수수료 전 수익"]))
c4.metric("영업수수료", won(allocation["영업수수료"]))
c5.metric("브이젠 1년차 순수익", won(cashflow.iloc[0]["브이젠 순수익"]))

st.caption(
    f"CP 인정계수 {pct(settlement['용량인정계수(RPCF×EFCR)'])} · "
    f"CP 인정물량 {settlement['CP 인정물량']:,.0f}kWh · 초기투자비 {won(p.rtu_cost+p.meter_cost)}"
)

left, right = st.columns([1.2, 1])
with left:
    item_df = pd.DataFrame({"정산항목": ["CP", "MEP", "MAP", "MWP", "IMB"], "금액(만원)": [settlement[k] / 10_000 for k in ["CP", "MEP", "MAP", "MWP", "IMB"]]})
    fig = go.Figure(go.Bar(x=item_df["정산항목"], y=item_df["금액(만원)"], marker_color=["#0f766e", "#2563eb", "#14b8a6", "#38bdf8", "#ef4444"]))
    fig.update_layout(title="정산항목별 1년차 효과", yaxis_title="만원", height=390, margin=dict(l=20, r=20, t=55, b=30))
    st.plotly_chart(fig, width="stretch")
with right:
    st.dataframe(pd.DataFrame({"항목": settlement.keys(), "값": settlement.values()}), width="stretch", hide_index=True, height=390)

st.subheader("연차별 누적 수익")
fig2 = go.Figure()
fig2.add_trace(go.Scatter(x=cashflow["연차"], y=cashflow["사업주 누적수익"] / 10_000, name="사업주 누적"))
fig2.add_trace(go.Scatter(x=cashflow["연차"], y=cashflow["브이젠 누적수익"] / 10_000, name="브이젠 누적"))
fig2.update_layout(yaxis_title="만원", xaxis_title="연차", height=390, legend=dict(orientation="h"))
st.plotly_chart(fig2, width="stretch")

with st.expander("연차별 상세 현금흐름", expanded=False):
    st.dataframe(cashflow, width="stretch", hide_index=True)

params_df = pd.DataFrame([asdict(p)])
download = BytesIO()
with pd.ExcelWriter(download, engine="openpyxl") as writer:
    params_df.to_excel(writer, sheet_name="입력값", index=False)
    cashflow.to_excel(writer, sheet_name="연차별현금흐름", index=False)
    pd.DataFrame([settlement | allocation]).to_excel(writer, sheet_name="1년차결과", index=False)
st.download_button("입력값·결과 Excel 다운로드", download.getvalue(), "vgen_vpp_simulation.xlsx", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

st.warning("본 결과는 영업 검토용 근사치입니다. 실제 정산은 최신 전력시장운영규칙과 KPX 정산자료를 기준으로 확인해야 합니다.")
