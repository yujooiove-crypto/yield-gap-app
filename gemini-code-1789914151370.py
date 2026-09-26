import streamlit as st
import yfinance as yf
import pandas as pd

st.set_page_config(
    page_title="국내주식 종목별 주요지표 분석",
    page_icon="📊",
    layout="wide"
)

# 1. 국내 주요 종목 한글명 <-> 6자리 코드 매핑 사전 (100+ 종목)
STOCK_MAP = {
    "삼성전자": "005930", "삼전": "005930", "삼성전자우": "005935",
    "sk하이닉스": "000660", "하이닉스": "000660", "하닉": "000660",
    "현대차": "005380", "현대자동차": "005380", "기아": "000270", "기아차": "000270",
    "lg에너지솔루션": "373220", "lg엔솔": "373220", "엔솔": "373220",
    "삼성바이오로직스": "207940", "삼바": "207940", "셀트리온": "068270",
    "알테오젠": "196170", "에코프로비엠": "247540", "에코프로bm": "247540",
    "에코프로": "086520", "포스코홀딩스": "005490", "posco홀딩스": "005490", "포스코": "005490",
    "naver": "035420", "네이버": "035420", "카카오": "035720",
    "삼양식품": "003230", "한화에어로스페이스": "012450", "한화에어로": "012450",
    "두산에너빌리티": "034020", "두산로보틱스": "454910", "크래프톤": "259960",
    "hpsp": "403870", "한미반도체": "042700", "리노공업": "058470",
    "kb금융": "105560", "신한지주": "055550", "하나금융지주": "086790",
    "우리금융지주": "316140", "메리츠금융지주": "138040", "카카오뱅크": "323410",
    "lg전자": "066570", "현대모비스": "012330", "삼성sdi": "006400", "lg화학": "051910",
    "kt&g": "033780", "kt": "030200", "sk텔레콤": "017670", "lg유플러스": "032640",
    "hlb": "028300", "삼천당제약": "000250", "한미약품": "128940", "유한양행": "000100",
    "하이브": "352820", "jyp ent.": "035900", "jyp": "035900", "에스엠": "041510",
    "와이지엔터테인먼트": "122870", "엔씨소프트": "036570", "레인보우로보틱스": "277810",
    "한국항공우주": "047810", "한국전력": "015760", "한온시스템": "018880", "루닛": "328130"
}

def get_clean_ticker(query):
    q = query.strip()
    clean_q = q.lower().replace(" ", "")
    code = STOCK_MAP.get(clean_q)
    if not code and q.isdigit():
        code = q.zfill(6)
    return code, q

# 2. 글로벌 금융망 데이터 조회 함수
@st.cache_data(ttl=300)
def load_global_kr_stock(code, display_name):
    data = {
        "code": code, "name": display_name, "market": "코스피",
        "price": 0, "change_pct": 0.0,
        "per": None, "fwd_per": None, "pbr": None, "div_yield": None,
        "roe": None, "op_margin": None, "net_margin": None,
        "debt_ratio": None, "curr_ratio": None,
        "rev_growth": None, "eps_growth": None
    }

    # 코스피(.KS) 우선 탐색 후 없으면 코스닥(.KQ) 탐색
    info = {}
    for sfx in [".KS", ".KQ"]:
        t_sym = f"{code}{sfx}"
        try:
            stk = yf.Ticker(t_sym)
            inf = stk.info
            p = inf.get("currentPrice") or inf.get("regularMarketPrice") or inf.get("previousClose")
            if p:
                info = inf
                data["market"] = "코스피 (KOSPI)" if sfx == ".KS" else "코스닥 (KOSDAQ)"
                break
        except Exception:
            continue

    if not info:
        return None

    # 주가 및 변동률
    data["name"] = info.get("shortName") or info.get("longName") or display_name
    curr_p = info.get("currentPrice") or info.get("regularMarketPrice") or info.get("previousClose") or 0
    data["price"] = int(curr_p)
    prev_p = info.get("previousClose")
    if prev_p and data["price"]:
        data["change_pct"] = round(((data["price"] - prev_p) / prev_p) * 100, 2)

    # 1) 가치평가
    data["per"] = info.get("trailingPE")
    data["fwd_per"] = info.get("forwardPE")
    data["pbr"] = info.get("priceToBook")
    dy = info.get("dividendYield")
    if dy is not None:
        data["div_yield"] = round(dy * 100 if dy < 0.2 else dy, 2)

    # 2) 수익성
    roe_val = info.get("returnOnEquity")
    if roe_val is not None:
        data["roe"] = round(roe_val * 100 if abs(roe_val) < 2.0 else roe_val, 1)

    # ROE 결측 시 공준 공식: (PBR / PER) * 100
    if data["roe"] is None and data["per"] and data["pbr"] and data["per"] > 0:
        data["roe"] = round((data["pbr"] / data["per"]) * 100, 1)

    opm = info.get("operatingMargins")
    if opm is not None:
        data["op_margin"] = round(opm * 100 if abs(opm) < 2.0 else opm, 1)

    npm = info.get("profitMargins")
    if npm is not None:
        data["net_margin"] = round(npm * 100 if abs(npm) < 2.0 else npm, 1)

    # 3) 재무건전성 & 성장성
    debt = info.get("debtToEquity")
    if debt is not None:
        data["debt_ratio"] = round(float(debt), 1)

    curr = info.get("currentRatio")
    if curr is not None:
        data["curr_ratio"] = round(float(curr) * 100 if float(curr) < 10.0 else float(curr), 1)

    rg = info.get("revenueGrowth")
    if rg is not None:
        data["rev_growth"] = round(float(rg) * 100, 1)

    eg = info.get("earningsGrowth")
    if eg is not None:
        data["eps_growth"] = round(float(eg) * 100, 1)

    return data

# --- 사이드바 ---
with st.sidebar:
    st.header("⚙️ 분석 기준 설정")
    deposit_rate = st.slider(
        "기준 예금 이자율 (%)", min_value=1.0, max_value=10.0, value=3.5, step=0.1,
        help="일드갭 산출 시 비교 기준이 되는 시중 정기예금/국고채 무위험 금리입니다."
    )
    st.divider()
    st.markdown("""
    **📖 벤저민 그레이엄 일드갭 판정 기준**
    - **+4.0%p 이상**: 매우 유리 (적극 매수)
    - **+2.0%p ~ +4.0%p**: 유리 (비중 확대)
    - **+1.0%p ~ +2.0%p**: 다소 유리 (선별 투자)
    - **0.0%p ~ +1.0%p**: 메리트 없음
    - **0.0%p 미만**: 매우 불리 (예금 보유)
    """)

# --- 메인 화면 ---
st.title("📈 국내주식 종목별 주요지표 분석")
st.caption("가치평가 · 수익성 · 재무건전성 및 성장성 종합 진단 (글로벌 무차단 금융망)")

# 빠른 조회 버튼
st.write("🔥 **인기 종목 빠른 선택:**")
btn_cols = st.columns(7)
popular_list = ["삼성전자", "SK하이닉스", "현대차", "기아", "알테오젠", "삼양식품", "셀트리온"]
for i, p_name in enumerate(popular_list):
    if btn_cols[i].button(p_name, use_container_width=True):
        st.session_state["active_query"] = p_name

if "active_query" not in st.session_state:
    st.session_state["active_query"] = "삼성전자"

col_search, col_btn = st.columns([4, 1])
with col_search:
    user_input = st.text_input(
        "종목명 또는 6자리 코드 입력",
        value=st.session_state["active_query"],
        help="목록에 없는 종목은 6자리 숫자 코드(예: 005930, 003230)를 입력하시면 즉시 분석됩니다."
    )
with col_btn:
    st.write("")
    st.write("")
    run_btn = st.button("종목 분석", type="primary", use_container_width=True)

if run_btn or user_input != st.session_state.get("last_searched"):
    st.session_state["last_searched"] = user_input
    code, display_name = get_clean_ticker(user_input)

    if not code:
        st.error(f"'{user_input}' 종목코드를 찾을 수 없습니다. 6자리 숫자 코드(예: 005930)를 직접 입력해 주세요.")
    else:
        with st.spinner(f"'{display_name}' ({code}) 금융 데이터를 집계 중입니다..."):
            d = load_global_kr_stock(code, display_name)

        if not d or d["price"] == 0:
            st.error(f"'{display_name}' ({code}) 종목의 시세 정보를 불러올 수 없습니다. 6자리 코드가 맞는지 확인해 주세요.")
        else:
            st.divider()
            h1, h2, h3 = st.columns([2, 1, 1])
            h1.subheader(f"🏢 {d['name']} ({d['code']})")
            h2.metric("현재 주가", f"{d['price']:,.0f}원", f"{d['change_pct']:+.2f}%" if d['change_pct'] != 0 else "")
            h3.write(f"**소속 시장:** `{d['market']}`")

            # 3대 분석 탭 구성 (수급 제거 완료)
            tab1, tab2, tab3 = st.tabs([
                "💰 1. 가치평가 지표 (일드갭)",
                "📈 2. 수익성 지표",
                "🛡️ 3. 재무건전성 & 성장성 지표"
            ])

            # ==========================================
            # TAB 1: 가치평가 (Valuation & 일드갭)
            # ==========================================
            with tab1:
                st.markdown("#### 기업 가치 대비 주가 수준 (Valuation)")
                v1, v2, v3, v4 = st.columns(4)
                v1.metric("PER (결산)", f"{d['per']:.1f}배" if d['per'] else "N/A", "15배 이하 저평가")
                v2.metric("PBR (순자산비율)", f"{d['pbr']:.2f}배" if d['pbr'] else "N/A", "1.0배 이하 청산가치")
                v3.metric("선행 PER (추정)", f"{d['fwd_per']:.1f}배" if d['fwd_per'] else f"{d['per']:.1f}배" if d['per'] else "N/A", "향후 이익 기준")
                v4.metric("배당수익률", f"{d['div_yield']:.2f}%" if d['div_yield'] is not None else "0.00%", "3% 이상 안전마진")

                st.markdown("##### 📌 벤저민 그레이엄 일드갭(초과수익률) 진단")
                base_per = d['fwd_per'] or d['per']
                if base_per and base_per > 0:
                    exp_ret = (1 / base_per) * 100
                    yield_gap = exp_ret - deposit_rate

                    yc1, yc2, yc3 = st.columns(3)
                    yc1.metric("주식 기대수익률 (1/PER)", f"{exp_ret:.2f}%", f"적용 PER {base_per:.1f}배")
                    yc2.metric("기준 예금 이자율", f"{deposit_rate:.2f}%")
                    yc3.metric("일드갭 (초과수익률)", f"{yield_gap:+.2f}%p")

                    if yield_gap >= 4.0:
                        st.success("🟢 **매우 유리 (주식 적극 매수 구간)** — 예금 대비 주식의 초과수익 보상이 4%p 이상으로 기대수익이 매우 높습니다.")
                    elif yield_gap >= 2.0:
                        st.info("🔵 **유리 (주식 비중 확대)** — 예금보다 2~4%p 높은 수익률이 기대되는 안정적 투자 구간입니다.")
                    elif yield_gap >= 1.0:
                        st.warning("🟡 **다소 유리 (선별 투자)** — 예금 대비 1~2%p 초과수익 구간으로 실적 점검이 필요합니다.")
                    elif yield_gap >= 0.0:
                        st.warning("🟠 **메리트 없음 (분산 권장)** — 주식 위험 대비 보상이 적어 예금·채권 병행이 유리합니다.")
                    else:
                        st.error("🔴 **매우 불리 (예금 보유 유리)** — 주식 기대수익률이 무위험 예금 금리보다 낮습니다.")
                else:
                    st.info("적자 기업이거나 PER 산출이 어려워 일드갭 계산을 생략합니다.")

                with st.expander("📖 가치평가 지표 상세 설명"):
                    st.markdown("""
                    * **PER (주가수익비율)**: 현재 주가를 1주당 순이익(EPS)으로 나눈 값으로, 낮을수록 이익 대비 주가가 저렴함을 뜻합니다.
                    * **PBR (주가순자산비율)**: 현재 주가를 1주당 순자산(BPS)으로 나눈 값으로, 1.0배 미만이면 순자산 청산가치보다 저평가된 상태입니다.
                    * **일드갭 (Yield Gap)**: 주식 기대수익률(1/PER)에서 은행 예금/국채 금리를 뺀 초과수익률로 안전자산 대비 주식의 보상 매력도를 측정합니다.
                    """)

            # ==========================================
            # TAB 2: 수익성 (Profitability)
            # ==========================================
            with tab2:
                st.markdown("#### 돈을 버는 효율성과 마진율 (Profitability)")
                p1, p2, p3 = st.columns(3)
                p1.metric("ROE (자기자본이익률)", f"{d['roe']:.1f}%" if d['roe'] is not None else "N/A", "10% 이상 우량")
                p2.metric("영업이익률", f"{d['op_margin']:.1f}%" if d['op_margin'] is not None else "N/A", "본업 경쟁력")
                p3.metric("순이익률", f"{d['net_margin']:.1f}%" if d['net_margin'] is not None else "N/A", "최종 마진")

                if d['roe'] is not None and d['roe'] >= 10:
                    st.success(f"✅ **수익성 우수**: ROE가 `{d['roe']:.1f}%`로 자기자본 대비 복리 수익 창출력이 매우 우수합니다.")
                elif d['roe'] is not None:
                    st.info(f"ℹ️ **수익성 보통**: ROE가 `{d['roe']:.1f}%` 수준입니다.")

                with st.expander("📖 수익성 지표 상세 설명"):
                    st.markdown("""
                    * **ROE (자기자본이익률)**: 주주들이 투자한 순자본으로 1년간 얼마의 순이익을 창출했는지 측정하는 대표 수익성 지표입니다. (10~15% 이상 우수)
                    * **영업이익률**: 매출액 중 원가와 판관비를 제하고 남은 순수 영업이익 비율로, 브랜드 가격 결정력과 마진 방어력을 보여줍니다.
                    * **순이익률**: 금융비용과 법인세까지 모두 제하고 최종 주주 몫으로 남은 순이익 비율입니다.
                    """)

            # ==========================================
            # TAB 3: 재무건전성 & 성장성 (Stability & Growth)
            # ==========================================
            with tab3:
                st.markdown("#### 재무적 생존 체력과 사업 확장성 (Stability & Growth)")
                s1, s2, s3, s4 = st.columns(4)
                s1.metric("부채비율", f"{d['debt_ratio']:.1f}%" if d['debt_ratio'] is not None else "N/A", "100% 이하 안정권")
                s2.metric("유동비율", f"{d['curr_ratio']:.1f}%" if d['curr_ratio'] is not None else "N/A", "100% 이상 권장")
                s3.metric("매출 증가율 (YoY)", f"{d['rev_growth']:+.1f}%" if d['rev_growth'] is not None else "N/A", "외형 성장")
                s4.metric("순익 증가율 (YoY)", f"{d['eps_growth']:+.1f}%" if d['eps_growth'] is not None else "N/A", "이익 성장")

                if d['debt_ratio'] is not None and d['debt_ratio'] <= 100:
                    st.success(f"✅ **재무구조 우량**: 부채비율이 `{d['debt_ratio']:.1f}%`로 고금리 국면에서도 매우 안전합니다.")
                elif d['debt_ratio'] is not None and d['debt_ratio'] > 200:
                    st.warning(f"⚠️ **부채비율 주의**: 부채비율이 `{d['debt_ratio']:.1f}%`로 이자 부담을 점검할 필요가 있습니다.")

                with st.expander("📖 재무건전성 및 성장성 지표 상세 설명"):
                    st.markdown("""
                    * **부채비율**: 자기자본 대비 총부채 비율입니다. 100% 이하가 이상적이며, 낮을수록 재무 안정성이 높습니다.
                    * **유동비율**: 1년 안에 현금화할 수 있는 유동자산으로 단기 부채를 갚을 수 있는 능력(100% 이상 권장)입니다.
                    * **매출/순익 증가율**: 전년 대비 사업 규모와 순이익의 확장세를 보여주는 핵심 성장 지표입니다.
                    """)
