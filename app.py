from __future__ import annotations

from dataclasses import asdict, dataclass
from io import BytesIO

import pandas as pd
import plotly.graph_objects as go
import streamlit as st


DEFAULT_EXTRA_REVENUE_PER_MW = 14_000_000
DEFAULT_IMBP_PER_MW = 1_000_000
DEFAULT_RTU_COST = 1_500_000
DEFAULT_NEW_METER_COST = 1_500_000


@dataclass(frozen=True)
class Inputs:
    capacity_mw: float
    cp_factor: float
    rpcf: float
    extra_revenue_per_mw: float
    imbp_per_mw: float
    owner_share: float
    channel_enabled: bool
    channel_fee_rate: float
    rtu_required: bool
    new_meter_required: bool
    rtu_cost: float
    new_meter_cost: float


def calculate(p: Inputs) -> dict[str, float]:
    gross_extra = p.capacity_mw * p.extra_revenue_per_mw * p.cp_factor * p.rpcf
    imbp = p.capacity_mw * p.imbp_per_mw
    distributable = gross_extra - imbp
    owner_before_infra = distributable * p.owner_share
    vgen_before_channel = distributable * (1 - p.owner_share)
    channel_fee = max(vgen_before_channel, 0) * p.channel_fee_rate if p.channel_enabled else 0.0
    owner_infra = (p.rtu_cost if p.rtu_required else 0) + (p.new_meter_cost if p.new_meter_required else 0)
    return {
        "총 VPP 추가수익": gross_extra,
        "IMBP 차감": imbp,
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


st.set_page_config(page_title="V-GEN VPP 수익 계산기", page_icon="⚡", layout="wide")
st.markdown(
    """
<style>
.block-container {max-width: 1320px; padding-top: 1.4rem; padding-bottom: 3rem}
.hero {padding: 1.7rem 2rem; border-radius: 22px; color:white; margin-bottom:1.1rem;
 background:linear-gradient(120deg,#082846,#075985,#0f766e)}
.hero h1{font-size:2rem;margin:0}.hero p{margin:.5rem 0 0;opacity:.93}
.metric{border:1px solid #dbe4ee;border-top:5px solid #2563eb;border-radius:16px;
 padding:1.1rem;background:#fff;min-height:140px;box-shadow:0 5px 16px rgba(15,23,42,.05)}
.metric.green{border-top-color:#16a34a}.metric.orange{border-top-color:#f59e0b}
.metric.red{border-top-color:#dc2626}.metric.navy{border-top-color:#0f3b61}
.label{color:#64748b;font-size:.85rem;font-weight:700}.value{font-size:1.85rem;font-weight:850;
 color:#102a43;margin:.4rem 0}.note{color:#64748b;font-size:.78rem;line-height:1.4}
.formula{padding:1rem 1.25rem;border-radius:14px;background:#eff6ff;border-left:5px solid #2563eb}
</style>
<div class="hero"><h1>V-GEN VPP 수익 계산기</h1>
<p>용량, CP 계수, RPCF만 바꿔 발전사업주·브이젠·영업채널 수익을 즉시 확인합니다.</p></div>
""",
    unsafe_allow_html=True,
)

st.subheader("1. 핵심 입력")
i1, i2, i3 = st.columns(3)
with i1:
    capacity_mw = st.number_input("발전소 용량(MW)", min_value=0.01, max_value=1000.0, value=1.0, step=0.1)
with i2:
    cp_factor_pct = st.number_input("CP 계수(%)", min_value=0.0, max_value=200.0, value=100.0, step=1.0,
                                    help="기준 CP 수익 대비 적용 비율입니다. 100%가 기준값입니다.")
with i3:
    rpcf_pct = st.number_input("RPCF(%)", min_value=0.0, max_value=200.0, value=100.0, step=1.0,
                               help="성과연동형용량가격계수입니다. 100%가 기준값입니다.")

with st.expander("계약·비용 설정", expanded=True):
    c1, c2, c3 = st.columns(3)
    with c1:
        owner_share_pct = st.slider("발전사업주 배분율(%)", 0, 100, 50)
        channel_enabled = st.toggle("영업채널 계약 적용", value=False)
        channel_fee_pct = st.number_input("영업채널 수수료율(브이젠 몫 기준, %)", 0.0, 100.0, 20.0, 1.0,
                                          disabled=not channel_enabled)
    with c2:
        rtu_required = st.checkbox("RTU 설치 필요", value=True)
        rtu_cost = st.number_input("RTU 비용(발전사업주 부담, 원)", 0, 100_000_000, DEFAULT_RTU_COST, 100_000,
                                   disabled=not rtu_required)
        new_meter_required = st.checkbox("신자취 설치 필요", value=True)
        new_meter_cost = st.number_input("신자취 비용(발전사업주 부담, 원)", 0, 100_000_000, DEFAULT_NEW_METER_COST, 100_000,
                                         disabled=not new_meter_required)
    with c3:
        extra_revenue_per_mw = st.number_input("기준 총 추가수익(원/MW·년)", 0, 100_000_000, DEFAULT_EXTRA_REVENUE_PER_MW, 100_000)
        imbp_per_mw = st.number_input("IMBP 차감액(원/MW·년)", 0, 100_000_000, DEFAULT_IMBP_PER_MW, 100_000)
        st.caption("기본값: 총 추가수익 1,400만원/MW·년, IMBP 100만원/MW·년")

p = Inputs(
    capacity_mw=capacity_mw,
    cp_factor=cp_factor_pct / 100,
    rpcf=rpcf_pct / 100,
    extra_revenue_per_mw=float(extra_revenue_per_mw),
    imbp_per_mw=float(imbp_per_mw),
    owner_share=owner_share_pct / 100,
    channel_enabled=channel_enabled,
    channel_fee_rate=channel_fee_pct / 100,
    rtu_required=rtu_required,
    new_meter_required=new_meter_required,
    rtu_cost=float(rtu_cost if rtu_required else 0),
    new_meter_cost=float(new_meter_cost if new_meter_required else 0),
)
r = calculate(p)

st.markdown(
    f'<div class="formula"><b>기본 계산:</b> {capacity_mw:,.2f}MW × '
    f'{manwon(extra_revenue_per_mw)}/MW × CP {cp_factor_pct:,.1f}% × RPCF {rpcf_pct:,.1f}% '
    f'= <b>{manwon(r["총 VPP 추가수익"])}</b> → IMBP {manwon(r["IMBP 차감"])} 차감 → '
    f'<b>배분대상 {manwon(r["배분대상 순수익"])}</b></div>',
    unsafe_allow_html=True,
)

st.subheader("2. 기본 수익 배분")
a, b, c, d = st.columns(4)
with a:
    metric_card("총 VPP 추가수익", r["총 VPP 추가수익"], "CP 계수와 RPCF 반영 전력시장 추가수익", "navy")
with b:
    metric_card("IMBP 차감", -r["IMBP 차감"], "50:50 배분 전에 우선 차감", "red")
with c:
    metric_card("발전사업주 배분액", r["발전사업주 배분액"], f"순수익의 {owner_share_pct}%", "green")
with d:
    metric_card("브이젠 배분액", r["브이젠 배분액"], f"순수익의 {100-owner_share_pct}%", "blue")

st.subheader("3. 영업채널 및 설치비 반영")
e, f, g, h = st.columns(4)
with e:
    metric_card("영업채널 수수료", r["영업채널 수수료"],
                f"브이젠 배분액의 {channel_fee_pct:.0f}%" if channel_enabled else "영업채널 미적용", "orange")
with f:
    metric_card("브이젠 최종수익", r["브이젠 최종수익"], "브이젠 배분액 - 채널수수료", "blue")
with g:
    metric_card("발전사업주 설치비", -r["발전사업주 RTU·신자취 부담"], "RTU·신자취는 발전사업주 부담", "red")
with h:
    metric_card("발전사업주 1년차 실수익", r["발전사업주 1년차 실수익"], "배분액 - RTU·신자취", "green")

chart_df = pd.DataFrame({
    "구분": ["총 추가수익", "IMBP", "발전사업주 배분", "브이젠 배분", "채널수수료", "발전사업주 설치비"],
    "금액(만원)": [r["총 VPP 추가수익"], -r["IMBP 차감"], r["발전사업주 배분액"],
                  r["브이젠 배분액"], -r["영업채널 수수료"], -r["발전사업주 RTU·신자취 부담"]],
})
chart_df["금액(만원)"] /= 10_000
fig = go.Figure(go.Bar(x=chart_df["구분"], y=chart_df["금액(만원)"],
                       marker_color=["#0f3b61", "#dc2626", "#16a34a", "#2563eb", "#f59e0b", "#ef4444"],
                       text=[f"{v:,.0f}" for v in chart_df["금액(만원)"]], textposition="outside"))
fig.update_layout(height=410, yaxis_title="만원/년", margin=dict(l=20, r=20, t=30, b=40))
st.plotly_chart(fig, width="stretch")

st.subheader("4. 용량별 빠른 비교")
capacities = sorted(set([0.5, 1.0, 3.0, 5.0, 10.0, round(capacity_mw, 2)]))
rows = []
for cap in capacities:
    cap_result = calculate(Inputs(**(asdict(p) | {"capacity_mw": cap})))
    rows.append({
        "용량(MW)": cap,
        "총 추가수익(만원)": cap_result["총 VPP 추가수익"] / 10_000,
        "IMBP(만원)": cap_result["IMBP 차감"] / 10_000,
        "발전사업주 배분액(만원)": cap_result["발전사업주 배분액"] / 10_000,
        "브이젠 배분액(만원)": cap_result["브이젠 배분액"] / 10_000,
        "채널수수료(만원)": cap_result["영업채널 수수료"] / 10_000,
        "브이젠 최종수익(만원)": cap_result["브이젠 최종수익"] / 10_000,
    })
quick_df = pd.DataFrame(rows)
st.dataframe(quick_df.round(1), width="stretch", hide_index=True)

download = BytesIO()
with pd.ExcelWriter(download, engine="openpyxl") as writer:
    pd.DataFrame([asdict(p)]).to_excel(writer, sheet_name="입력값", index=False)
    pd.DataFrame([r]).to_excel(writer, sheet_name="계산결과", index=False)
    quick_df.to_excel(writer, sheet_name="용량별비교", index=False)
st.download_button("계산 결과 Excel 다운로드", download.getvalue(), "vgen_vpp_profit.xlsx",
                   "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

st.info("기본 1MW·CP 100%·RPCF 100% 기준: 총 1,400만원 → IMBP 100만원 차감 → 50:50 각 650만원. 영업채널 적용 시 브이젠 몫의 20%를 채널에 지급합니다.")
