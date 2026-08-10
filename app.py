from __future__ import annotations

from dataclasses import asdict, dataclass
from io import BytesIO

import pandas as pd
import plotly.graph_objects as go
import streamlit as st


OFFICIAL_JEJU_RCP = 22.05
DEFAULT_APPLIED_CP = 14.0
DEFAULT_SOLAR_EFFECTIVE_CAPACITY = 5.20
DEFAULT_RTU_COST = 1_500_000
DEFAULT_NEW_METER_COST = 1_500_000
MONTHS = ["1월", "2월", "3월", "4월", "5월", "6월", "7월", "8월", "9월", "10월", "11월", "12월"]
SOLAR_RATIOS = [1.96, 2.30, 2.46, 2.35, 4.04, 9.00, 10.38, 9.94, 9.21, 5.41, 2.98, 2.34]


@dataclass(frozen=True)
class Inputs:
    capacity_mw: float
    cp_price: float
    effective_capacity_ratio: float
    rpcf: float
    imbp_total: float
    other_revenue: float
    owner_share: float
    channel_enabled: bool
    channel_fee_rate: float
    rtu_required: bool
    new_meter_required: bool
    rtu_cost: float
    new_meter_cost: float


def annual_cp_revenue(capacity_mw: float, cp_price: float, effective_capacity_ratio: float, rpcf: float) -> float:
    """KPX 제주 급전가능재생e 상시(24시간) 실효용량 기준 연간 CP 추정."""
    return capacity_mw * 1_000 * 8_760 * effective_capacity_ratio * cp_price * rpcf


def calculate(p: Inputs) -> dict[str, float]:
    cp_revenue = annual_cp_revenue(p.capacity_mw, p.cp_price, p.effective_capacity_ratio, p.rpcf)
    gross_extra = cp_revenue + p.other_revenue
    distributable = gross_extra - p.imbp_total
    owner_before_infra = distributable * p.owner_share
    vgen_before_channel = distributable * (1 - p.owner_share)
    channel_fee = max(vgen_before_channel, 0) * p.channel_fee_rate if p.channel_enabled else 0.0
    owner_infra = (p.rtu_cost if p.rtu_required else 0) + (p.new_meter_cost if p.new_meter_required else 0)
    return {
        "CP 용량정산금": cp_revenue,
        "기타 추가정산": p.other_revenue,
        "총 VPP 추가수익": gross_extra,
        "IMBP 차감": p.imbp_total,
        "배분대상 순수익": distributable,
        "발전사업주 배분액": owner_before_infra,
        "브이젠 배분액": vgen_before_channel,
        "영업채널 수수료": channel_fee,
        "발전사업주 RTU·신자취 부담": owner_infra,
        "발전사업주 1년차 실수익": owner_before_infra - owner_infra,
        "브이젠 최종수익": vgen_before_channel - channel_fee,
    }


def manwon(value: float) -> str:
    return f"{value / 10_000:,.0f}만원"


def metric_card(label: str, value: float, note: str, tone: str = "blue") -> None:
    st.markdown(
        f'<div class="metric {tone}"><div class="label">{label}</div>'
        f'<div class="value">{manwon(value)}</div><div class="note">{note}</div></div>',
        unsafe_allow_html=True,
    )


st.set_page_config(page_title="V-GEN 제주 VPP 수익 계산기", page_icon="⚡", layout="wide")
st.markdown(
    """
<style>
.block-container {max-width:1320px;padding-top:1.4rem;padding-bottom:3rem}
.hero {padding:1.7rem 2rem;border-radius:22px;color:white;margin-bottom:1.1rem;background:linear-gradient(120deg,#082846,#075985,#0f766e)}
.hero h1{font-size:2rem;margin:0}.hero p{margin:.5rem 0 0;opacity:.93}
.metric{border:1px solid #dbe4ee;border-top:5px solid #2563eb;border-radius:16px;padding:1.1rem;background:#fff;min-height:140px;box-shadow:0 5px 16px rgba(15,23,42,.05)}
.metric.green{border-top-color:#16a34a}.metric.orange{border-top-color:#f59e0b}.metric.red{border-top-color:#dc2626}.metric.navy{border-top-color:#0f3b61}
.label{color:#64748b;font-size:.85rem;font-weight:700}.value{font-size:1.85rem;font-weight:850;color:#102a43;margin:.4rem 0}.note{color:#64748b;font-size:.78rem;line-height:1.4}
.formula{padding:1rem 1.25rem;border-radius:14px;background:#eff6ff;border-left:5px solid #2563eb;margin:.6rem 0 1rem}
</style>
<div class="hero"><h1>V-GEN 제주 VPP 수익 계산기</h1><p>제주 입찰시장 운영기준에 따라 CP 용량정산금부터 50:50 배분까지 한눈에 계산합니다.</p></div>
""",
    unsafe_allow_html=True,
)

st.subheader("1. 세 가지만 먼저 입력하세요")
i1, i2, i3 = st.columns(3)
with i1:
    capacity_mw = st.number_input("발전소 용량(MW)", 0.01, 1000.0, 1.0, 0.1)
with i2:
    cp_price = st.number_input("적용 CP 단가(원/kWh)", 0.0, 100.0, DEFAULT_APPLIED_CP, 0.1,
                               help="요청 기준은 14원입니다. 2026/27 공식 제주 RCP는 22.05원/kWh입니다.")
with i3:
    rpcf_pct = st.number_input("RPCF(%)", 0.0, 200.0, 100.0, 1.0,
                               help="발전소별 적용값을 입력하세요. 일률적인 공식 기본값은 없습니다.")

baseline_14 = annual_cp_revenue(capacity_mw, 14.0, DEFAULT_SOLAR_EFFECTIVE_CAPACITY / 100, rpcf_pct / 100)
baseline_official = annual_cp_revenue(capacity_mw, OFFICIAL_JEJU_RCP, DEFAULT_SOLAR_EFFECTIVE_CAPACITY / 100, rpcf_pct / 100)
b1, b2 = st.columns(2)
with b1:
    st.info(f"CP 14원 기준 예상 CP 수익: **{manwon(baseline_14)} / 년**")
with b2:
    st.info(f"공식 제주 RCP 22.05원 기준: **{manwon(baseline_official)} / 년**")

with st.expander("세부 가정·계약·비용 설정", expanded=True):
    c1, c2, c3 = st.columns(3)
    with c1:
        effective_capacity_pct = st.number_input("태양광 실효용량비율(%)", 0.0, 100.0, DEFAULT_SOLAR_EFFECTIVE_CAPACITY, 0.1,
                                                  help="2026/27 제주 태양광 월별 값의 공식 평균 5.20%")
        imbp_total = st.number_input("예상 IMBP 차감액(원/년)", 0, 1_000_000_000, 0, 100_000,
                                     help="실제 예측오차와 시장가격에 따라 달라지므로 예상액을 직접 입력합니다.")
        other_revenue = st.number_input("기타 추가정산 MEP·MAP·MWP 등(원/년)", 0, 1_000_000_000, 0, 100_000)
    with c2:
        owner_share_pct = st.slider("발전사업주 배분율(%)", 0, 100, 50)
        channel_enabled = st.toggle("영업채널 계약 적용", value=False)
        channel_fee_pct = st.number_input("영업수수료율(브이젠 몫 기준, %)", 0.0, 100.0, 20.0, 1.0, disabled=not channel_enabled)
        st.caption("IMBP 차감 후 순수익을 50:50 배분하고, 영업수수료는 브이젠 몫에서만 지급합니다.")
    with c3:
        rtu_required = st.checkbox("RTU 설치 필요", value=True)
        rtu_cost = st.number_input("RTU 비용(발전사업주 부담, 원)", 0, 100_000_000, DEFAULT_RTU_COST, 100_000, disabled=not rtu_required)
        new_meter_required = st.checkbox("신자취 설치 필요", value=True)
        new_meter_cost = st.number_input("신자취 비용(발전사업주 부담, 원)", 0, 100_000_000, DEFAULT_NEW_METER_COST, 100_000, disabled=not new_meter_required)

p = Inputs(
    capacity_mw=capacity_mw, cp_price=cp_price, effective_capacity_ratio=effective_capacity_pct / 100,
    rpcf=rpcf_pct / 100, imbp_total=float(imbp_total), other_revenue=float(other_revenue),
    owner_share=owner_share_pct / 100, channel_enabled=channel_enabled, channel_fee_rate=channel_fee_pct / 100,
    rtu_required=rtu_required, new_meter_required=new_meter_required,
    rtu_cost=float(rtu_cost if rtu_required else 0), new_meter_cost=float(new_meter_cost if new_meter_required else 0),
)
r = calculate(p)

st.markdown(
    f'<div class="formula"><b>운영기준 산식:</b> {capacity_mw:,.2f}MW × 1,000 × 8,760시간 × '
    f'{effective_capacity_pct:.2f}% × {cp_price:.2f}원/kWh × RPCF {rpcf_pct:.1f}% '
    f'= <b>{manwon(r["CP 용량정산금"])}</b><br>CP + 기타정산 - IMBP = '
    f'<b>배분대상 {manwon(r["배분대상 순수익"])}</b></div>', unsafe_allow_html=True,
)

st.subheader("2. 연간 수익과 50:50 배분")
a, b, c, d = st.columns(4)
with a: metric_card("CP 용량정산금", r["CP 용량정산금"], "24시간 × 실효용량비율 × CP단가 × RPCF", "navy")
with b: metric_card("IMBP 차감", -r["IMBP 차감"], "실적 가정값, 50:50 배분 전 차감", "red")
with c: metric_card("발전사업주 배분액", r["발전사업주 배분액"], f"배분대상의 {owner_share_pct}%", "green")
with d: metric_card("브이젠 배분액", r["브이젠 배분액"], f"배분대상의 {100-owner_share_pct}%", "blue")

st.subheader("3. 수수료와 설치비 반영")
e, f, g, h = st.columns(4)
with e: metric_card("영업채널 수수료", r["영업채널 수수료"], f"브이젠 몫의 {channel_fee_pct:.0f}%" if channel_enabled else "미적용", "orange")
with f: metric_card("브이젠 최종수익", r["브이젠 최종수익"], "브이젠 배분액 - 영업수수료")
with g: metric_card("발전사업주 설치비", -r["발전사업주 RTU·신자취 부담"], "RTU·신자취 각 150만원 기본", "red")
with h: metric_card("발전사업주 1년차 실수익", r["발전사업주 1년차 실수익"], "배분액 - 설치비", "green")

chart_df = pd.DataFrame({"구분": ["CP", "기타정산", "IMBP", "발전사업주", "브이젠", "채널수수료"],
                         "금액(만원)": [r["CP 용량정산금"], r["기타 추가정산"], -r["IMBP 차감"], r["발전사업주 배분액"], r["브이젠 배분액"], -r["영업채널 수수료"]]})
chart_df["금액(만원)"] /= 10_000
fig = go.Figure(go.Bar(x=chart_df["구분"], y=chart_df["금액(만원)"], marker_color=["#0f3b61", "#0f766e", "#dc2626", "#16a34a", "#2563eb", "#f59e0b"], text=[f"{v:,.0f}" for v in chart_df["금액(만원)"]], textposition="outside"))
fig.update_layout(height=390, yaxis_title="만원/년", margin=dict(l=20, r=20, t=30, b=40))
st.plotly_chart(fig, width="stretch")

with st.expander("공식 제주 태양광 월별 실효용량비율 보기"):
    official_df = pd.DataFrame({"월": MONTHS, "실효용량비율(%)": SOLAR_RATIOS})
    st.dataframe(official_df, width="stretch", hide_index=True)
    st.caption("KPX 2026/27 적용값(2026.7.1~2027.6.30), 평균 5.20%")

st.subheader("4. 용량별 빠른 비교")
rows = []
for cap in sorted(set([0.5, 1.0, 3.0, 5.0, 10.0, round(capacity_mw, 2)])):
    cr = calculate(Inputs(**(asdict(p) | {"capacity_mw": cap})))
    rows.append({"용량(MW)": cap, "CP 수익(만원)": cr["CP 용량정산금"] / 10_000, "배분대상(만원)": cr["배분대상 순수익"] / 10_000,
                 "발전사업주(만원)": cr["발전사업주 배분액"] / 10_000, "브이젠(만원)": cr["브이젠 배분액"] / 10_000, "브이젠 최종(만원)": cr["브이젠 최종수익"] / 10_000})
quick_df = pd.DataFrame(rows)
st.dataframe(quick_df.round(1), width="stretch", hide_index=True)

download = BytesIO()
with pd.ExcelWriter(download, engine="openpyxl") as writer:
    pd.DataFrame([asdict(p)]).to_excel(writer, sheet_name="입력값", index=False)
    pd.DataFrame([r]).to_excel(writer, sheet_name="계산결과", index=False)
    quick_df.to_excel(writer, sheet_name="용량별비교", index=False)
    pd.DataFrame({"월": MONTHS, "태양광 실효용량비율(%)": SOLAR_RATIOS}).to_excel(writer, sheet_name="공식기준", index=False)
st.download_button("계산 결과 Excel 다운로드", download.getvalue(), "vgen_jeju_vpp_profit.xlsx", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

st.warning("본 계산은 CP 용량정산금의 사업성 추정입니다. RPCF·IMBP·기타정산은 자원별 실적과 시장가격에 따라 달라지므로 실제 정산서와 차이가 날 수 있습니다.")
st.caption("기준: KPX 제주 급전가능재생e 용량정산금 개편(2026.4.1 시행), 2026/27 제주 실효용량비율 및 기준용량가격")
