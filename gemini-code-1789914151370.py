import streamlit as st
import yfinance as yf
import pandas as pd
import requests
from bs4 import BeautifulSoup
import re

st.set_page_config(page_title="주식 일드갭 & 지표 진단기", page_icon="📈", layout="centered")

# --- 네이버 증권 국내 주식 크롤링 함수 ---
def get_naver_stock_data(code):
    url = f"https://finance.naver.com/item/main.naver?code={code}"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }
    res = requests.get(url, headers=headers, timeout=5)
    res.encoding = "cp949"
    soup = BeautifulSoup(res.text, "html.parser")

    # 1. 기업명
    name = code
    wrap_company = soup.find("div", class_="wrap_company")
    if wrap_company and wrap_company.find("h2"):
        name = wrap_company.find("h2").text.strip()

    # 2. 현재 주가
    price = None
    no_today = soup.find("p", class_="no_today")
    if no_today and no_today.find("span", class_="blind"):
        price_text = no_today.find("span", class_="blind").text.replace(",", "")
        if price_text.isdigit():
            price = int(price_text)

    # 3. PER, EPS, PBR, 배당수익률 (FnGuide 기준 공식 공시 데이터)
    per, eps, pbr, div_yield = None, None, None, None

    per_tag = soup.find(id="_per")
    if per_tag:
        t = per_tag.text.replace(",", "").strip()
        try: per = float(t)
        except ValueError: per = None

    eps_tag = soup.find(id="_eps")
    if eps_tag:
        t = eps_tag.text.replace(",", "").strip()
        try: eps = float(t)
        except ValueError: eps = None

    pbr_tag = soup.find(id="_pbr")
    if pbr_tag:
        t = pbr_tag.text.replace(",", "").strip()
        try: pbr = float(t)
        except ValueError: pbr = None

    dvr_tag = soup.find(id="_dvr")
    if dvr_tag:
        t = dvr_tag.text.replace(",", "").strip()
        try: div_yield = float(t)
        except ValueError: div_yield = None

    # ROE 역산: (PBR / PER) * 100
    roe = None
    if per and pbr and per > 0:
        roe = (pbr / per) * 100

    return {
        "name": name,
        "price": price,
        "per": per,
        "eps": eps,
        "pbr": pbr,
        "roe": roe,
        "div_yield": div_yield
    }

# --- 사이드바: 기준 금리 설정 ---
with st.sidebar:
    st.header("⚙️ 기준 금리 설정")
    deposit_rate = st.slider(
        "기준 예금 이자율 (무위험 금리, %)",
        min_value=1.0, max_value=10.0, value=3.5, step=0.1
    )
    st.caption("시중은행 1년 정기예금 또는 국채 금리를 입력하세요.")
    st.markdown("---")
    st.markdown("""
    **📖 벤저민 그레이엄 일드갭 기준**
    - **+4.0%p 이상**: 매우 유리 (적극 매수)
    - **+2.0%p ~ +4.0%p**: 유리 (비중 확대)
    - **+1.0%p ~ +2.0%p**: 다소 유리 (선별 투자)
    - **0.0%p ~ +1.0%p**: 메리트 없음
    - **0.0%p 미만**: 매우 불리 (예금 보유)
    """)

# --- 메인 화면 ---
st.title("📊 주식 투자 유불리 & 재무 진단기")
st.write("국내 주식(네이버 증권 FnGuide) 및 미국 주식 지표를 기반으로 정확한 일드갭을 산출합니다.")

market_col1, market_col2 = st.columns([1, 2])
with market_col1:
    market_type = st.selectbox("시장 구분", ["국내 주식 (코스피/코스닥)", "미국 주식"])

with market_col2:
    if market_type.startswith("국내"):
        ticker_input = st.text_input("종목코드 6자리 입력", value="005930", help="예: 삼성전자 005930, SK하이닉스 000660")
    else:
        ticker_input = st.text_input("티커(Ticker) 심볼 입력", value="AAPL", help="예: AAPL, MSFT, NVDA")

if st.button("종목 분석 실행", type="primary", use_container_width=True):
    raw_code = ticker_input.strip()
    if not raw_code:
        st.warning("종목코드를 입력해 주세요.")
    else:
        with st.spinner("최신 재무 데이터를 불러오는 중..."):
            try:
                if market_type.startswith("국내"):
                    data = get_naver_stock_data(raw_code)
                    currency = "KRW"
                else:
                    ticker = raw_code.upper()
                    stock = yf.Ticker(ticker)
                    info = stock.info
                    data = {
                        "name": info.get("shortName") or ticker,
                        "price": info.get("currentPrice") or info.get("regularMarketPrice"),
                        "per": info.get("trailingPE"),
                        "eps": info.get("trailingEps"),
                        "pbr": info.get("priceToBook"),
                        "roe": (info.get("returnOnEquity") * 100) if info.get("returnOnEquity") else None,
                        "div_yield": (info.get("dividendYield") * 100) if info.get("dividendYield") else None
                    }
                    currency = "USD"

                if not data["price"]:
                    st.error("종목 정보를 찾을 수 없습니다. 종목코드를 다시 확인해 주세요.")
                else:
                    st.session_state["stock_data"] = data
                    st.session_state["currency"] = currency
                    st.session_state["code"] = raw_code
            except Exception as e:
                st.error(f"데이터 조회 중 오류 발생: {e}")

# 결과 표시 섹션
if "stock_data" in st.session_state:
    data = st.session_state["stock_data"]
    currency = st.session_state["currency"]
    code = st.session_state["code"]

    st.divider()
    st.subheader(f"🏢 {data['name']} ({code})")

    price_str = f"{data['price']:,.0f}원" if currency == "KRW" else f"${data['price']:,.2f}"
    st.metric(label="현재 주가", value=price_str)

    # 1. 일드갭 계산 섹션
    st.markdown("### 1. 벤저민 그레이엄 일드갭 분석")
    
    # PER 직접 수정 시뮬레이션 지원
    default_per = float(data['per']) if data['per'] and data['per'] > 0 else 10.0
    calc_per = st.number_input("분석에 적용할 PER (배)", min_value=0.1, max_value=200.0, value=default_per, step=0.1)

    stock_return = (1 / calc_per) * 100
    yield_gap = stock_return - deposit_rate

    col1, col2, col3 = st.columns(3)
    col1.metric("주식 예상수익률 (1/PER)", f"{stock_return:.2f}%", f"적용 PER {calc_per:.1f}배")
    col2.metric("예금 이자율 (기준)", f"{deposit_rate:.2f}%")
    col3.metric("일드갭 (초과수익률)", f"{yield_gap:+.2f}%p")

    # 판정 기준
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

    # 2. 4대 투자 지표 진단 섹션
    st.markdown("### 2. 네이버 증권 핵심 재무 지표")
    d_col1, d_col2 = st.columns(2)

    with d_col1:
        if data['per']:
            st.write(f"📌 **FnGuide 공시 PER**: `{data['per']:.1f}배`")
        if data['pbr']:
            st.write(f"📌 **PBR**: `{data['pbr']:.2f}배` {'(저평가)' if data['pbr'] <= 1.0 else ''}")
        if data['eps']:
            eps_str = f"{data['eps']:,.0f}원" if currency == "KRW" else f"${data['eps']:,.2f}"
            st.write(f"📌 **EPS (주당순이익)**: `{eps_str}`")

    with d_col2:
        if data['roe']:
            st.write(f"📌 **추정 ROE**: `{data['roe']:.1f}%` {'(우수)' if data['roe'] >= 10 else ''}")
        if data['div_yield']:
            st.write(f"📌 **배당수익률**: `{data['div_yield']:.2f}%` {'(고배당)' if data['div_yield'] >= 3.0 else ''}")
        else:
            st.write("📌 **배당수익률**: `0.00%` (무배당 또는 정보 없음)")
