# V-GEN VPP 수익 계산기

재생에너지 입찰시장 영업 검토용 Streamlit 계산기입니다.

## 반영 사항

- 육지 EFCR 기본값: 태양광 12.78%, 5시간 ESS 81.865%
- RPCF와 EFCR 개별 수정 및 `RPCF × EFCR` CP 인정계수 반영
- CP/MEP/MAP/MWP/IMB와 발전계획·실적 비율 전체 직접 입력
- 기본 배분 및 IMB 차감 후 50:50 순수익 계약
- 영업수수료를 계약 배분·IMB 반영 후 브이젠 양(+)의 수익에 적용
- RTU와 신자취 각각 150만원 기본 투자비 및 직접 수정
- 연차별 현금흐름과 Excel 다운로드

## 실행

```bash
pip install -r requirements.txt
streamlit run app.py
```

실제 전력시장 정산은 거래시간별 자료를 사용합니다. 본 계산기는 연간 등가 영업 시뮬레이션이며 실제 정산서를 대체하지 않습니다.
