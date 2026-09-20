import streamlit as st
import yfinance as yf
import pandas as pd

st.set_page_config(page_title="주식 일드갭 & 지표 진단기", page_icon="📈", layout="centered")

# --- 사이드바: 기준 금리 설정 ---
with st.sidebar:
    st.header("⚙️ 기준 금리 설정")
    deposit_rate = st.slider(
        "기준 예금 이자율 (무위험 금리, %)",
        min_value=1.0,
        max_value=10.0,
        value=3.5,
        step=0.1
    )
    st.caption("시중은행 1년 정기예금 또는 국채 3년물 금리를 입력하세요.")
    st.markdown("---")
    st.markdown("""
    **📖 벤저민 그레이엄 일드갭 기준**
    - **+4.0%p 이상**: 매우 유리 (적극 매수)
    - **+2.0%p ~ +4.0%p**: 유리 (비중 확대)
    - **+1.0%p ~ +2.0%p**: 다소 유리 (선별 투자)
    - **0.0%p ~ +1.0%p**: 메리트 없음
    - **0.0%p 미만**: 매우 불리 (예금 보유)
    """)

# --- 메인 화면 헤더 ---
st.title("📊 주식 투자 유불리 & 재무 진단기")
st.write("종목코드를 입력하면 일드갭과 4대 투자 지표를 종합 분석합니다.")

# 종목 입력 방식
market_col1, market_col2 = st.columns([1, 2])
with market_col1:
    market_type = st.selectbox("시장 구분", ["국내 주식 (코스피/코스닥)", "미국 주식"])

with market_col2:
    if market_type == "국내 주식 (코스피/코스닥)":
        ticker_input = st.text_input("종목코드 6자리 입력", value="005930", help="코스피는 숫자 6자리(예: 005930), 코스닥은 종목코드 입력")
        # 야후 파이낸스용 티커 포맷 자동 변환 (코스피 .KS / 코스닥 .KQ)
        default_ticker = f"{ticker_input.strip()}.KS"
    else:
        ticker_input = st.text_input("티커(Ticker) 심볼 입력", value="AAPL", help="예: AAPL, MSFT, NVDA, GOOGL")
        default_ticker = ticker_input.strip().upper()

run_btn = st.button("종목 분석 실행", type="primary", use_container_width=True)

if run_btn:
    with st.spinner("금융 데이터를 조회 중입니다..."):
        try:
            stock = yf.Ticker(default_ticker)
            info = stock.info

            # 코스피 조회 실패 시 코스닥(.KQ) 시도
            if ("regularMarketPrice" not in info or info.get("regularMarketPrice") is None) and market_type.startswith("국내"):
                default_ticker = f"{ticker_input.strip()}.KQ"
                stock = yf.Ticker(default_ticker)
                info = stock.info

            # 지표 추출
            name = info.get("shortName") or info.get("longName") or default_ticker
            currency = info.get("currency", "KRW")
            curr_price = info.get("currentPrice") or info.get("regularMarketPrice")
            per = info.get("trailingPE")
            eps = info.get("trailingEps")
            pbr = info.get("priceToBook")
            roe = info.get("returnOnEquity")
            div_yield = info.get("dividendYield")

            if curr_price is None:
                st.error("종목 정보를 찾을 수 없습니다. 종목코드나 티커를 다시 확인해 주세요.")
            else:
                st.divider()
                st.subheader(f"🏢 {name} ({default_ticker})")

                # 가격 정보
                price_format = f"{curr_price:,.0f}원" if currency == "KRW" else f"${curr_price:,.2f}"
                st.metric(label="현재 주가", value=price_format)

                # 1. 일드갭 계산 섹션
                st.markdown("### 1. 벤저민 그레이엄 일드갭 분석")
                if per and per > 0:
                    stock_return = (1 / per) * 100
                    yield_gap = stock_return - deposit_rate

                    col1, col2, col3 = st.columns(3)
                    col1.metric("주식 예상수익률 (1/PER)", f"{stock_return:.2f}%", f"PER {per:.1f}배")
                    col2.metric("예금 이자율 (기준)", f"{deposit_rate:.2f}%")
                    col3.metric("일드갭 (초과수익률)", f"{yield_gap:+.2f}%p")

                    # 판정 결과 배지
                    if yield_gap >= 4.0:
                        st.success("🟢 **매우 유리 (주식 적극 매수 구간)** — 예금 금리 대비 초과수익 보상이 4%p 이상으로 주식 매력도가 매우 높습니다.")
                    elif yield_gap >= 2.0:
                        st.info("🔵 **유리 (주식 비중 확대)** — 예금보다 2~4%p 높은 수익률이 기대되는 안정적 구간입니다.")
                    elif yield_gap >= 1.0:
                        st.warning("🟡 **다소 유리 (선별 투자)** — 예금 대비 1~2%p 수준의 프리미엄으로 개별 기업의 펀더멘털 선별이 필요합니다.")
                    elif yield_gap >= 0.0:
                        st.warning("🟠 **메리트 없음 (분산 권장)** — 주식 위험 대비 보상이 낮아 예금·채권 병행이 유리합니다.")
                    else:
                        st.error("🔴 **매우 불리 (확정금리 자산 보유 유리)** — 주식 기대수익률이 무위험 예금 금리보다 낮습니다.")
                else:
                    st.warning("해당 종목은 최근 당기순손실(적자) 상태이거나 PER 데이터를 산정할 수 없어 일드갭 계산에서 제외됩니다.")

                # 2. 4대 투자 적합성 지표 진단 섹션
                st.markdown("### 2. 핵심 투자 지표 진단")
                diag_col1, diag_col2 = st.columns(2)

                with diag_col1:
                    # PER 진단
                    if per and 0 < per <= 15:
                        st.write(f"✅ **PER**: `{per:.1f}배` (15배 이하 저평가 통과)")
                    elif per and per > 15:
                        st.write(f"⚠️ **PER**: `{per:.1f}배` (15배 초과 다소 고평가)")
                    else:
                        st.write(f"❌ **PER**: `{per or '적자'}`")

                    # PBR 진단
                    if pbr and 0 < pbr <= 1.0:
                        st.write(f"✅ **PBR**: `{pbr:.2f}배` (1.0배 이하 순자산 대비 저평가)")
                    elif pbr:
                        st.write(f"ℹ️ **PBR**: `{pbr:.2f}배` (순자산 가치 상회)")
                    else:
                        st.write("➖ **PBR**: 정보 없음")

                with diag_col2:
                    # ROE 진단
                    if roe:
                        roe_pct = roe * 100 if roe < 1 else roe
                        if roe_pct >= 10:
                            st.write(f"✅ **ROE**: `{roe_pct:.1f}%` (10% 이상 우수 수익성)")
                        else:
                            st.write(f"⚠️ **ROE**: `{roe_pct:.1f}%` (10% 미만 보통)")
                    else:
                        st.write("➖ **ROE**: 정보 없음")

                    # 배당수익률 진단
                    if div_yield:
                        dy_pct = div_yield * 100 if div_yield < 0.2 else div_yield
                        if dy_pct >= 3.0:
                            st.write(f"✅ **배당수익률**: `{dy_pct:.1f}%` (3% 이상 고배당 안전마진)")
                        else:
                            st.write(f"ℹ️ **배당수익률**: `{dy_pct:.1f}%`")
                    else:
                        st.write("➖ **배당수익률**: 무배당 또는 데이터 없음")

        except Exception as e:
            st.error(f"데이터를 불러오는 중 오류가 발생했습니다: {e}")