from __future__ import annotations

from dataclasses import asdict, dataclass
from io import BytesIO

import pandas as pd
import plotly.graph_objects as go
import streamlit as st


DEFAULT_RTU_COST = 1_500_000
DEFAULT_NEW_METER_COST = 1_500_000
PRESETS = {
    ("육지", "태양광"): {"efcr": 12.78, "cp": 14.00, "rpcf": 100.0, "note": "육지 중립값 — 제주 태양광 RPCF 평균 105.08% 참고"},
    ("제주", "태양광"): {"efcr": 5.20, "cp": 22.05, "rpcf": 105.08, "note": "2026/27 EFCR·RCP, 26-1차 태양광 RPCF 평균"},
    ("제주", "풍력"): {"efcr": 16.10, "cp": 22.05, "rpcf": 94.81, "note": "2026/27 EFCR·RCP, 26-1차 풍력 RPCF 평균"},
    ("육지", "풍력"): {"efcr": 16.10, "cp": 14.00, "rpcf": 94.81, "note": "제주 풍력 RPCF 평균 참고 — 확정값 직접 입력"},
}


@dataclass(frozen=True)
class Inputs:
    capacity_mw: float
    cp_price: float
    effective_capacity_ratio: float
    rpcf: float
    mwp_per_mw: float
    map_per_mw: float
    imbp_per_mw: float
    base_revenue_per_mw: float
    owner_share: float
    channel_enabled: bool
    channel_fee_rate: float
    rtu_required: bool
    new_meter_required: bool
    rtu_cost: float
    new_meter_cost: float


def annual_cp_revenue(capacity_mw: float, cp_price: float, effective_capacity_ratio: float, rpcf: float) -> float:
    return capacity_mw * 1_000 * 8_760 * effective_capacity_ratio * cp_price * rpcf


def calculate(p: Inputs) -> dict[str, float]:
    cp = annual_cp_revenue(p.capacity_mw, p.cp_price, p.effective_capacity_ratio, p.rpcf)
    mwp = p.capacity_mw * p.mwp_per_mw
    map_value = p.capacity_mw * p.map_per_mw
    imbp = p.capacity_mw * p.imbp_per_mw
    gross_extra = cp + mwp + map_value
    distributable = gross_extra - imbp
    owner = distributable * p.owner_share
    vgen = distributable * (1 - p.owner_share)
    channel_fee = max(vgen, 0) * p.channel_fee_rate if p.channel_enabled else 0.0
    infra = (p.rtu_cost if p.rtu_required else 0) + (p.new_meter_cost if p.new_meter_required else 0)
    base_revenue = p.capacity_mw * p.base_revenue_per_mw
    return {
        "기본 전력·REC 수익": base_revenue,
        "CP 용량정산금": cp,
        "MWP": mwp,
        "MAP": map_value,
        "IMBP 차감": imbp,
        "총 추가정산": gross_extra,
        "배분대상 순수익": distributable,
        "발전사업주 배분액": owner,
        "브이젠 배분액": vgen,
        "영업채널 수수료": channel_fee,
        "발전사업주 RTU·신자취 부담": infra,
        "발전사업주 1년차 추가수익": owner - infra,
        "발전사업주 총수익 참고": base_revenue + owner,
        "브이젠 최종수익": vgen - channel_fee,
    }


def manwon(value: float) -> str:
    return f"{value / 10_000:,.0f}만원"


def metric_card(label: str, value: float, note: str, tone: str = "blue") -> None:
    st.markdown(
        f'<div class="metric {tone}"><div class="label">{label}</div>'
        f'<div class="value">{manwon(value)}</div><div class="note">{note}</div></div>',
        unsafe_allow_html=True,
    )


st.set_page_config(page_title="V-GEN 재생에너지 입찰시장 수익 계산기", page_icon="⚡", layout="wide")
st.markdown(
    """
<style>
.block-container{max-width:1340px;padding-top:1.3rem;padding-bottom:3rem}
.hero{padding:1.7rem 2rem;border-radius:22px;color:white;margin-bottom:1.1rem;background:linear-gradient(120deg,#082846,#075985,#0f766e)}
.hero h1{font-size:2rem;margin:0}.hero p{margin:.5rem 0 0;opacity:.93}
.metric{border:1px solid #dbe4ee;border-top:5px solid #2563eb;border-radius:16px;padding:1.05rem;background:#fff;min-height:140px;box-shadow:0 5px 16px rgba(15,23,42,.05)}
.metric.green{border-top-color:#16a34a}.metric.orange{border-top-color:#f59e0b}.metric.red{border-top-color:#dc2626}.metric.navy{border-top-color:#0f3b61}
.label{color:#64748b;font-size:.84rem;font-weight:700}.value{font-size:1.78rem;font-weight:850;color:#102a43;margin:.4rem 0}.note{color:#64748b;font-size:.77rem;line-height:1.4}
.formula{padding:1rem 1.25rem;border-radius:14px;background:#eff6ff;border-left:5px solid #2563eb;margin:.6rem 0 1rem;line-height:1.7}
</style>
<div class="hero"><h1>V-GEN 재생에너지 입찰시장 수익 계산기</h1><p>기본 전력·REC 수익은 보호하고, CP·MWP·MAP−IMBP 추가수익만 계약 배분합니다.</p></div>
""", unsafe_allow_html=True,
)

st.subheader("1. 발전소 기준 선택")
s1, s2, s3 = st.columns([1, 1, 2])
with s1:
    region = st.selectbox("지역", ["육지", "제주"])
with s2:
    resource = st.selectbox("자원", ["태양광", "풍력"])
preset = PRESETS[(region, resource)]
with s3:
    st.info(
        f"**{region} {resource} 기본값:** 실효용량 {preset['efcr']:.2f}% · "
        f"CP {preset['cp']:.2f}원 · RPCF {preset['rpcf']:.0f}%  \n{preset['note']}"
    )

st.subheader("2. 핵심 입력")
i1, i2, i3, i4 = st.columns(4)
with i1:
    capacity_mw = st.number_input("발전소 용량(MW)", 0.01, 1000.0, 1.0, 0.1)
with i2:
    effective_capacity_pct = st.number_input("실효용량비율(%)", 0.0, 100.0, float(preset["efcr"]), 0.01, key=f"efcr-{region}-{resource}")
with i3:
    cp_price = st.number_input("적용 CP 단가(원/kWh)", 0.0, 100.0, float(preset["cp"]), 0.1, key=f"cp-{region}-{resource}")
with i4:
    rpcf_pct = st.number_input("RPCF(%)", 0.0, 200.0, float(preset["rpcf"]), 1.0, key=f"rpcf-{region}-{resource}")

with st.expander("추가정산·기본수익·계약 설정", expanded=True):
    c1, c2, c3 = st.columns(3)
    with c1:
        st.markdown("**입찰시장 추가정산 가정**")
        mwp_per_mw = st.number_input("MWP(원/MW·년)", 0, 100_000_000, 500_000, 100_000)
        map_per_mw = st.number_input("MAP(원/MW·년)", 0, 100_000_000, 500_000, 100_000)
        imbp_per_mw = st.number_input("IMBP 차감(원/MW·년)", 0, 100_000_000, 800_000, 100_000)
        st.caption("태양광 기준 사업성 가정입니다. 실제 정산자료가 있으면 변경하세요.")
    with c2:
        st.markdown("**기본수익 및 계약**")
        base_revenue_per_mw = st.number_input("SMP/PPA+REC 기본수익(원/MW·년)", 0, 1_000_000_000, 0, 1_000_000,
                                              help="참고표시만 하며 VPP 추가수익 배분에는 포함하지 않습니다.")
        owner_share_pct = st.slider("발전사업주 배분율(%)", 0, 100, 50)
        channel_enabled = st.toggle("영업채널 계약 적용", value=False)
        channel_fee_pct = st.number_input("영업수수료율(브이젠 몫 기준, %)", 0.0, 100.0, 20.0, 1.0, disabled=not channel_enabled)
    with c3:
        st.markdown("**발전사업주 초기 부담**")
        rtu_required = st.checkbox("RTU 설치 필요", value=True)
        rtu_cost = st.number_input("RTU 비용(원)", 0, 100_000_000, DEFAULT_RTU_COST, 100_000, disabled=not rtu_required)
        new_meter_required = st.checkbox("신자취 설치 필요", value=True)
        new_meter_cost = st.number_input("신자취 비용(원)", 0, 100_000_000, DEFAULT_NEW_METER_COST, 100_000, disabled=not new_meter_required)

p = Inputs(
    capacity_mw=capacity_mw, cp_price=cp_price, effective_capacity_ratio=effective_capacity_pct / 100,
    rpcf=rpcf_pct / 100, mwp_per_mw=float(mwp_per_mw), map_per_mw=float(map_per_mw),
    imbp_per_mw=float(imbp_per_mw), base_revenue_per_mw=float(base_revenue_per_mw),
    owner_share=owner_share_pct / 100, channel_enabled=channel_enabled, channel_fee_rate=channel_fee_pct / 100,
    rtu_required=rtu_required, new_meter_required=new_meter_required,
    rtu_cost=float(rtu_cost if rtu_required else 0), new_meter_cost=float(new_meter_cost if new_meter_required else 0),
)
r = calculate(p)

st.markdown(
    f'<div class="formula"><b>① CP:</b> {capacity_mw:,.2f}MW × 1,000 × 8,760시간 × {effective_capacity_pct:.2f}% × '
    f'{cp_price:.2f}원 × RPCF {rpcf_pct:.1f}% = <b>{manwon(r["CP 용량정산금"])}</b><br>'
    f'<b>② 배분대상:</b> CP {manwon(r["CP 용량정산금"])} + MWP {manwon(r["MWP"])} + MAP {manwon(r["MAP"])} '
    f'− IMBP {manwon(r["IMBP 차감"])} = <b>{manwon(r["배분대상 순수익"])}</b><br>'
    f'<b>③ 기본 전력·REC 수익 {manwon(r["기본 전력·REC 수익"])}</b>은 위 추가수익 배분에서 제외</div>', unsafe_allow_html=True,
)

st.subheader("3. 입찰시장 추가수익")
a, b, c, d, e = st.columns(5)
with a: metric_card("CP", r["CP 용량정산금"], "실효용량·CP단가·RPCF 반영", "navy")
with b: metric_card("MWP", r["MWP"], "추가정산 가정", "green")
with c: metric_card("MAP", r["MAP"], "추가정산 가정", "green")
with d: metric_card("IMBP", -r["IMBP 차감"], "배분 전 차감", "red")
with e: metric_card("배분대상 순수익", r["배분대상 순수익"], "CP+MWP+MAP−IMBP", "orange")

st.subheader("4. 50:50 계약 및 비용")
f, g, h, j = st.columns(4)
with f: metric_card("발전사업주 배분액", r["발전사업주 배분액"], f"순수 추가수익의 {owner_share_pct}%", "green")
with g: metric_card("브이젠 배분액", r["브이젠 배분액"], f"순수 추가수익의 {100-owner_share_pct}%")
with h: metric_card("영업채널 수수료", r["영업채널 수수료"], f"브이젠 몫의 {channel_fee_pct:.0f}%" if channel_enabled else "미적용", "orange")
with j: metric_card("브이젠 최종수익", r["브이젠 최종수익"], "브이젠 배분액−영업수수료")

k, l, m = st.columns(3)
with k: metric_card("발전사업주 설치비", -r["발전사업주 RTU·신자취 부담"], "RTU·신자취 발전사업주 부담", "red")
with l: metric_card("발전사업주 1년차 추가수익", r["발전사업주 1년차 추가수익"], "배분액−초기 설치비", "green")
with m: metric_card("발전사업주 2년차 이후", r["발전사업주 배분액"], "초기 설치비 제외", "green")

chart_df = pd.DataFrame({
    "구분": ["CP", "MWP", "MAP", "IMBP", "발전사업주", "브이젠", "채널수수료"],
    "금액(만원)": [r["CP 용량정산금"], r["MWP"], r["MAP"], -r["IMBP 차감"], r["발전사업주 배분액"], r["브이젠 배분액"], -r["영업채널 수수료"]],
})
chart_df["금액(만원)"] /= 10_000
fig = go.Figure(go.Bar(
    x=chart_df["구분"], y=chart_df["금액(만원)"],
    marker_color=["#0f3b61", "#0f766e", "#16a34a", "#dc2626", "#22c55e", "#2563eb", "#f59e0b"],
    text=[f"{v:,.0f}" for v in chart_df["금액(만원)"]], textposition="outside",
))
fig.update_layout(height=390, yaxis_title="만원/년", margin=dict(l=20, r=20, t=30, b=40))
st.plotly_chart(fig, width="stretch")

st.subheader("5. 용량별 빠른 비교")
rows = []
for cap in sorted(set([0.5, 1.0, 3.0, 5.0, 10.0, round(capacity_mw, 2)])):
    cr = calculate(Inputs(**(asdict(p) | {"capacity_mw": cap})))
    rows.append({"용량(MW)": cap, "CP(만원)": cr["CP 용량정산금"] / 10_000, "순수 추가수익(만원)": cr["배분대상 순수익"] / 10_000,
                 "발전사업주(만원)": cr["발전사업주 배분액"] / 10_000, "브이젠(만원)": cr["브이젠 배분액"] / 10_000,
                 "채널수수료(만원)": cr["영업채널 수수료"] / 10_000, "브이젠 최종(만원)": cr["브이젠 최종수익"] / 10_000})
quick_df = pd.DataFrame(rows)
st.dataframe(quick_df.round(1), width="stretch", hide_index=True)

with st.expander("산정 근거와 주의사항"):
    st.markdown("""
- 어음풍력 21MW 2024년 5~11월 실적: CP 단순 연환산 약 1,454만원/MW·년, MWP·MAP 포함 약 1,622만원/MW·년.
- 육지 태양광은 풍력 실적을 그대로 적용하지 않고 실효용량 12.78%, RPCF 90%, MWP·MAP·IMBP 별도 가정을 사용합니다.
- MEP는 기본 에너지정산이며 장기계약의 SMP/PPA·REC 수익 구조에 따라 보정될 수 있어 VPP 추가수익 배분에서 제외합니다.
- 육지 확대 제도의 최종 운영규칙 및 발전소별 RPCF가 확정되면 해당 값으로 변경해야 합니다.
""")
    st.markdown("**2026년 1차 제주 RPCF 분포(적용기간 2026년 4~8월)**")
    st.dataframe(pd.DataFrame([
        {"자원 구분": "태양광 16개", "평균": 105.08, "중앙값": 106.33, "최소": 90.89, "최대": 118.33},
        {"자원 구분": "풍력 7개", "평균": 94.81, "중앙값": 94.33, "최소": 87.46, "최대": 103.47},
        {"자원 구분": "태양광·풍력 혼합 5개", "평균": 109.93, "중앙값": 112.88, "최소": 100.04, "최대": 116.05},
    ]), width="stretch", hide_index=True)
    st.caption("어음풍력 RPCF 103.47%. 육지 기본 100%는 확정값이 아닌 중립 사업성 가정입니다.")

download = BytesIO()
with pd.ExcelWriter(download, engine="openpyxl") as writer:
    pd.DataFrame([{"지역": region, "자원": resource} | asdict(p)]).to_excel(writer, sheet_name="입력값", index=False)
    pd.DataFrame([r]).to_excel(writer, sheet_name="계산결과", index=False)
    quick_df.to_excel(writer, sheet_name="용량별비교", index=False)
st.download_button("계산 결과 Excel 다운로드", download.getvalue(), "vgen_vpp_profit.xlsx", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

st.warning("본 계산은 사업성 추정입니다. MWP·MAP·IMBP와 RPCF는 자원별 실제 정산값에 따라 달라집니다.")
