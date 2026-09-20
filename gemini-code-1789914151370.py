import streamlit as st
import yfinance as yf
import pandas as pd

st.set_page_config(page_title="일드갭 주식 유불리 진단기", page_icon="📈", layout="centered")

# 국내 주요 종목 한글 매핑 딕셔너리
KOREA_STOCKS = {
    "삼성전자": "005930.KS", "sk하이닉스": "000660.KS", "현대차": "005380.KS",
    "기아": "000270.KS", "lg에너지솔루션": "373220.KS", "삼성바이오로직스": "207940.KS",
    "삼성전자우": "005935.KS", "셀트리온": "068270.KS", "kb금융": "105560.KS",
    "신한지주": "055550.KS", "포스코홀딩스": "005490.KS", "posco홀딩스": "005490.KS",
    "naver": "035420.KS", "네이버": "035420.KS", "카카오": "035720.KS",
    "에코프로비엠": "247540.KQ", "에코프로": "086520.KQ", "알테오젠": "196170.KQ",
    "hlb": "028300.KQ", "삼천당제약": "000250.KQ", "한미반도체": "042700.KS"
}

# --- 사이드바: 기준 금리 설정 ---
with st.sidebar:
    st.header("⚙️ 기준 금리 설정")
    deposit_rate = st.slider(
        "기준 예금 이자율 (무위험 금리, %)",
        min_value=1.0, max_value=10.0, value=3.5, step=0.1
    )
    st.caption("시중은행 1년 정기예금 또는 국고채 금리를 입력하세요.")
    st.markdown("---")
    st.markdown("""
    **📖 벤저민 그레이엄 일드갭 판정 기준**
    - **+4.0%p 이상**: 매우 유리 (적극 매수)
    - **+2.0%p ~ +4.0%p**: 유리 (비중 확대)
    - **+1.0%p ~ +2.0%p**: 다소 유리 (선별 투자)
    - **0.0%p ~ +1.0%p**: 메리트 없음
    - **0.0%p 미만**: 매우 불리 (예금 보유)
    """)

# --- 메인 화면 ---
st.title("📊 일드갭 기반 주식 유불리 진단기")
st.write("종목을 검색하면 주가와 재무 지표를 불러와 벤저민 그레이엄 일드갭을 계산합니다.")

market_col1, market_col2 = st.columns([1, 2])
with market_col1:
    market_type = st.selectbox("시장 구분", ["국내 주식 (코스피/코스닥)", "미국 주식"])

with market_col2:
    if market_type.startswith("국내"):
        search_input = st.text_input("종목명 또는 6자리 코드", value="삼성전자", help="한글 종목명(예: 삼성전자, SK하이닉스) 또는 6자리 숫자 코드(예: 005930)")
    else:
        search_input = st.text_input("미국 티커 심볼", value="AAPL", help="예: AAPL, NVDA, MSFT, TSLA")

if st.button("종목 분석 실행", type="primary", use_container_width=True):
    raw_query = search_input.strip()
    if not raw_query:
        st.warning("종목명 또는 코드를 입력해 주세요.")
    else:
        with st.spinner("해외 클라우드 최적화 엔진으로 금융 데이터를 조회 중입니다..."):
            stock_info = None
            ticker_symbol = ""
            matched_name = raw_query

            try:
                # 1. 티커 심볼 매핑
                if market_type.startswith("국내"):
                    query_lower = raw_query.lower()
                    if query_lower in KOREA_STOCKS:
                        ticker_symbol = KOREA_STOCKS[query_lower]
                    elif raw_query.isdigit() and len(raw_query) == 6:
                        ticker_symbol = f"{raw_query}.KS"
                    else:
                        ticker_symbol = f"{raw_query}.KS"

                    # 데이터 조회 시도
                    stock = yf.Ticker(ticker_symbol)
                    info = stock.info

                    # 코스피 조회 실패 시 코스닥(.KQ) 시도
                    if not info or not info.get("shortName"):
                        alt_ticker = ticker_symbol.replace(".KS", ".KQ")
                        alt_stock = yf.Ticker(alt_ticker)
                        alt_info = alt_stock.info
                        if alt_info and alt_info.get("shortName"):
                            ticker_symbol = alt_ticker
                            info = alt_info

                else:
                    ticker_symbol = raw_query.upper()
                    stock = yf.Ticker(ticker_symbol)
                    info = stock.info

                # 2. 현재 주가 추출
                curr_price = (
                    info.get("currentPrice")
                    or info.get("regularMarketPrice")
                    or info.get("previousClose")
                )

                if curr_price is None and stock:
                    try:
                        curr_price = float(stock.fast_info.last_price)
                    except Exception:
                        pass

                if curr_price is None:
                    st.error(f"'{raw_query}'에 대한 주가 데이터를 찾을 수 없습니다. 6자리 종목코드(예: 005930)로 다시 시도해 주세요.")
                else:
                    matched_name = info.get("shortName") or info.get("longName") or raw_query
                    currency = info.get("currency", "KRW" if market_type.startswith("국내") else "USD")

                    # PER 지표 (선행 PER 우선, 없으면 과거 PER)
                    fwd_per = info.get("forwardPE")
                    trail_per = info.get("trailingPE")
                    best_per = fwd_per or trail_per

                    eps = info.get("trailingEps") or info.get("forwardEps")
                    pbr = info.get("priceToBook")
                    roe = (info.get("returnOnEquity") * 100) if info.get("returnOnEquity") else None
                    div_yield = (info.get("dividendYield") * 100) if info.get("dividendYield") else None

                    # 세션에 저장
                    st.session_state["stock_data"] = {
                        "name": matched_name,
                        "ticker": ticker_symbol,
                        "currency": currency,
                        "price": curr_price,
                        "best_per": float(best_per) if best_per and best_per > 0 else 10.0,
                        "fwd_per": fwd_per,
                        "trail_per": trail_per,
                        "eps": eps,
                        "pbr": pbr,
                        "roe": roe,
                        "div_yield": div_yield
                    }

            except Exception as e:
                st.error(f"데이터 조회 중 네트워크 오류 발생: {e}")

# --- 결과 출력 영역 ---
if "stock_data" in st.session_state:
    d = st.session_state["stock_data"]

    st.divider()
    st.subheader(f"🏢 {d['name']} ({d['ticker']})")

    price_text = f"{d['price']:,.0f}원" if d["currency"] == "KRW" else f"${d['price']:,.2f}"
    st.metric(label="현재 주가", value=price_text)

    # 1. 일드갭 계산 섹션
    st.markdown("### 1. 벤저민 그레이엄 일드갭 분석")

    # PER 입력 및 MTS 값으로 직접 수정 지원
    calc_per = st.number_input(
        "분석에 적용할 PER (배) — 증권사 MTS 수치로 직접 수정 가능",
        min_value=0.1,
        max_value=200.0,
        value=float(d["best_per"]),
        step=0.1,
        help="HTS/MTS에 표기된 선행 PER 또는 추정 PER을 입력하면 즉시 재계산됩니다."
    )

    # 벤저민 그레이엄 기대수익률 및 초과수익률 계산
    stock_return = (1 / calc_per) * 100
    yield_gap = stock_return - deposit_rate

    c1, c2, c3 = st.columns(3)
    c1.metric("주식 예상수익률 (1/PER)", f"{stock_return:.2f}%", f"적용 PER {calc_per:.1f}배")
    c2.metric("예금 이자율 (기준)", f"{deposit_rate:.2f}%")
    c3.metric("일드갭 (초과수익률)", f"{yield_gap:+.2f}%p")

    # 책 기준 5단계 판정
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

    # 2. 보조 참고 지표
    st.markdown("### 2. 참고 재무 지표")
    rc1, rc2 = st.columns(2)
    with rc1:
        if d.get("fwd_per"):
            st.write(f"📌 **12개월 선행 PER**: `{d['fwd_per']:.1f}배`")
        if d.get("trail_per"):
            st.write(f"📌 **과거 결산 PER**: `{d['trail_per']:.1f}배`")
        if d.get("pbr"):
            st.write(f"📌 **PBR**: `{d['pbr']:.2f}배` {'(저평가)' if d['pbr'] <= 1.0 else ''}")

    with rc2:
        if d.get("roe"):
            st.write(f"📌 **추정 ROE**: `{d['roe']:.1f}%` {'(우수)' if d['roe'] >= 10 else ''}")
        if d.get("div_yield"):
            st.write(f"📌 **배당수익률**: `{d['div_yield']:.2f}%` {'(고배당)' if d['div_yield'] >= 3.0 else ''}")
        else:
            st.write("📌 **배당수익률**: `무배당 / 미제공`")
