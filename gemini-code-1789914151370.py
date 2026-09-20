import streamlit as st
import yfinance as yf
import pandas as pd
import requests

st.set_page_config(
    page_title="국내주식 종목별 주요지표 분석",
    page_icon="📊",
    layout="wide"
)

# 대표 주요 종목 코드 사전 (한글 종목명 즉시 매핑)
POPULAR_STOCKS = {
    "삼성전자": "005930", "sk하이닉스": "000660", "현대차": "005380", "기아": "000270",
    "lg에너지솔루션": "373220", "삼성바이오로직스": "207940", "셀트리온": "068270",
    "kb금융": "105560", "신한지주": "055550", "포스코홀딩스": "005490", "posco홀딩스": "005490",
    "naver": "035420", "네이버": "035420", "카카오": "035720", "에코프로비엠": "247540",
    "에코프로": "086520", "알테오젠": "196170", "hlb": "028300", "삼천당제약": "000250",
    "한미반도체": "042700", "두산에너빌리티": "034020", "한화에어로스페이스": "012450",
    "크래프톤": "259960", "카카오뱅크": "323410", "lg전자": "066570", "현대모비스": "012330",
    "삼성sdi": "006400", "lg화학": "051910", "kt&g": "033780", "하나금융지주": "086790"
}

def resolve_code(query):
    q = query.strip()
    if q.isdigit() and len(q) == 6:
        return q
    clean_q = q.lower().replace(" ", "")
    return POPULAR_STOCKS.get(clean_q, q)

# 클라우드 무차단 금융 데이터 수집 함수
@st.cache_data(ttl=300)
def load_all_stock_metrics(code):
    data = {
        "name": code, "code": code, "market": "국내증시", "price": 0, "change_pct": 0.0,
        "per": None, "fwd_per": None, "pbr": None, "div_yield": None,
        "roe": None, "op_margin": None, "net_margin": None,
        "debt_ratio": None, "curr_ratio": None,
        "investor_list": []
    }

    # 1. 글로벌 금융 데이터망(Yahoo Finance) 조회 (코스피 .KS -> 코스닥 .KQ 순차 탐색)
    info = {}
    ticker_used = ""
    for suffix in [".KS", ".KQ"]:
        t_sym = f"{code}{suffix}"
        stk = yf.Ticker(t_sym)
        try:
            inf = stk.info
            if inf and (inf.get("currentPrice") or inf.get("regularMarketPrice") or inf.get("shortName")):
                info = inf
                ticker_used = t_sym
                data["market"] = "코스피 (KOSPI)" if suffix == ".KS" else "코스닥 (KOSDAQ)"
                break
        except Exception:
            continue

    if info:
        data["name"] = info.get("shortName") or info.get("longName") or code
        data["price"] = int(info.get("currentPrice") or info.get("regularMarketPrice") or info.get("previousClose") or 0)
        
        # 주가 변동률
        prev_close = info.get("previousClose")
        if prev_close and data["price"]:
            data["change_pct"] = round(((data["price"] - prev_close) / prev_close) * 100, 2)

        # 1) 가치평가 지표
        data["per"] = info.get("trailingPE")
        data["fwd_per"] = info.get("forwardPE")
        data["pbr"] = info.get("priceToBook")
        
        dy = info.get("dividendYield")
        if dy is not None:
            data["div_yield"] = round(dy * 100 if dy < 0.2 else dy, 2)

        # 2) 수익성 지표 (백분율 보정)
        roe_val = info.get("returnOnEquity")
        if roe_val is not None:
            data["roe"] = round(roe_val * 100 if abs(roe_val) < 2.0 else roe_val, 1)

        opm = info.get("operatingMargins")
        if opm is not None:
            data["op_margin"] = round(opm * 100 if abs(opm) < 2.0 else opm, 1)

        npm = info.get("profitMargins")
        if npm is not None:
            data["net_margin"] = round(npm * 100 if abs(npm) < 2.0 else npm, 1)

        # 3) 재무건전성 지표
        debt = info.get("debtToEquity")
        if debt is not None:
            data["debt_ratio"] = round(float(debt), 1)

        curr = info.get("currentRatio")
        if curr is not None:
            data["curr_ratio"] = round(curr * 100 if curr < 10.0 else curr, 1)

    # 지표 누락 시 보정 공식 적용
    if data["roe"] is None and data["per"] and data["pbr"] and data["per"] > 0:
        data["roe"] = round((data["pbr"] / data["per"]) * 100, 1)

    # 4. 수급 동향 수신 시도 (Daum / Naver API)
    try:
        d_headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
            "Referer": f"https://finance.daum.net/quotes/A{code}"
        }
        d_url = f"https://finance.daum.net/api/investor/days?symbolCode=A{code}&page=1&perPage=10"
        d_res = requests.get(d_url, headers=d_headers, timeout=3)
        if d_res.status_code == 200:
            d_json = d_res.json().get("data", [])
            inv_list = []
            for item in d_json[:10]:
                d_date = str(item.get("date", ""))[:10]
                c_p = data["price"] or int(item.get("tradePrice", 0))
                f_qty = int(item.get("foreignNetBuy", 0))
                i_qty = int(item.get("institutionNetBuy", 0))
                a_qty = int(item.get("individualNetBuy", 0))
                inv_list.append({
                    "날짜": d_date,
                    "종가(원)": c_p,
                    "외국인(억원)": round(f_qty * c_p / 100000000, 1),
                    "기관(억원)": round(i_qty * c_p / 100000000, 1),
                    "개인(억원)": round(a_qty * c_p / 100000000, 1)
                })
            data["investor_list"] = inv_list
    except Exception:
        pass

    return data

# --- 사이드바: 기준 금리 설정 ---
with st.sidebar:
    st.header("⚙️ 분석 기준 설정")
    deposit_rate = st.slider(
        "기준 예금 이자율 (%)", min_value=1.0, max_value=10.0, value=3.5, step=0.1,
        help="일드갭 산출 시 비교 기준이 되는 시중 정기예금/국고채 무위험 금리입니다."
    )
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
st.title("📈 국내주식 종목별 주요지표 분석")
st.caption("가치평가 · 수익성 · 재무건전성 종합 진단 및 최근 10영업일 수급 동향")

col_in, col_btn = st.columns([4, 1])
with col_in:
    user_input = st.text_input("종목명 또는 6자리 코드 입력", value="삼성전자", placeholder="예: 삼성전자, SK하이닉스, 현대차, 005930")
with col_btn:
    st.write("")
    st.write("")
    search_clicked = st.button("종목 분석", type="primary", use_container_width=True)

if search_clicked or "current_target" in st.session_state:
    if search_clicked:
        target = resolve_code(user_input)
        st.session_state["current_target"] = target
    else:
        target = st.session_state["current_target"]

    with st.spinner("글로벌 금융 데이터베이스에서 실시간 지표를 집계 중입니다..."):
        d = load_all_stock_metrics(target)

    if d["price"] == 0:
        st.error(f"'{user_input}' 종목 정보를 불러올 수 없습니다. 6자리 종목코드(예: 삼성전자 005930)를 입력해 주세요.")
        st.stop()

    st.divider()
    h1, h2, h3 = st.columns([2, 1, 1])
    h1.subheader(f"🏢 {d['name']} ({d['code']})")
    h2.metric("현재가", f"{d['price']:,.0f}원", f"{d['change_pct']:+.2f}%" if d['change_pct'] != 0 else "")
    h3.write(f"**소속 시장:** `{d['market']}`")

    tab1, tab2, tab3, tab4 = st.tabs([
        "💰 1. 가치평가 지표",
        "📈 2. 수익성 지표",
        "🛡️ 3. 재무건전성 지표",
        "👥 4. 최근 10영업일 수급 동향"
    ])

    # ==========================================
    # TAB 1: 가치평가
    # ==========================================
    with tab1:
        st.markdown("#### 기업 가치 대비 주가 수준 (Valuation)")
        v1, v2, v3, v4 = st.columns(4)
        v1.metric("PER (결산)", f"{d['per']:.1f}배" if d['per'] else "N/A", "15배 이하 저평가")
        v2.metric("PBR (순자산비율)", f"{d['pbr']:.2f}배" if d['pbr'] else "N/A", "1.0배 이하 청산가치")
        v3.metric("추정 PER (선행)", f"{d['fwd_per']:.1f}배" if d['fwd_per'] else "N/A", "컨센서스 기준")
        v4.metric("배당수익률", f"{d['div_yield']:.2f}%" if d['div_yield'] else "0.00%", "3% 이상 안전마진")

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
                st.success("🟢 **매우 유리 (주식 적극 매수 구간)** — 예금 금리 대비 주식 초과수익 보상이 4%p 이상으로 기대수익이 매우 높습니다.")
            elif yield_gap >= 2.0:
                st.info("🔵 **유리 (주식 비중 확대)** — 예금보다 2~4%p 높은 수익률이 기대되는 안정적 투자 구간입니다.")
            elif yield_gap >= 1.0:
                st.warning("🟡 **다소 유리 (선별 투자)** — 예금 대비 1~2%p 초과수익 구간으로 개별 기업의 실적 점검이 필요합니다.")
            elif yield_gap >= 0.0:
                st.warning("🟠 **메리트 없음 (분산 권장)** — 주식 위험 대비 보상이 적어 예금·채권 병행이 유리합니다.")
            else:
                st.error("🔴 **매우 불리 (예금 보유 유리)** — 주식 기대수익률이 무위험 예금 금리보다 낮아 확정금리 자산이 유리합니다.")
        else:
            st.info("적자 기업이거나 PER 데이터가 없어 일드갭 계산을 생략합니다.")

        with st.expander("📖 가치평가 지표 상세 설명"):
            st.markdown("""
            * **PER (주가수익비율)**: 주가를 1주당 순이익(EPS)으로 나눈 값으로, 낮을수록 벌어들이는 이익 대비 주가가 저평가되어 있음을 뜻합니다.
            * **PBR (주가순자산비율)**: 주가를 주당순자산(BPS)으로 나눈 수치로, 1.0배 미만이면 순자산 청산가치보다 싼 가격입니다.
            * **일드갭 (Yield Gap)**: 주식 기대수익률(1/PER)에서 은행 예금/국채 금리를 뺀 초과수익률로, 안전자산 대비 주식의 기대 보상을 측정합니다.
            """)

    # ==========================================
    # TAB 2: 수익성
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
            * **ROE (자기자본이익률)**: 주주 자본으로 1년간 얼마의 순이익을 남겼는지 측정하는 대표 수익성 지표입니다. (10~15% 이상 우수)
            * **영업이익률**: 매출액 중 원가와 판관비를 제하고 남은 순수 본업의 영업이익 비율로, 브랜드 가격 결정력을 보여줍니다.
            * **순이익률**: 금융비용과 세금까지 모두 납부한 뒤 최종 주주 몫으로 남은 순이익 비율입니다.
            """)

    # ==========================================
    # TAB 3: 재무건전성
    # ==========================================
    with tab3:
        st.markdown("#### 재무적 생존 체력과 부도 위험 (Stability)")
        s1, s2 = st.columns(2)
        s1.metric("부채비율", f"{d['debt_ratio']:.1f}%" if d['debt_ratio'] is not None else "N/A", "100% 이하 안정권")
        s2.metric("유동비율", f"{d['curr_ratio']:.1f}%" if d['curr_ratio'] is not None else "N/A", "100% 이상 권장")

        if d['debt_ratio'] is not None and d['debt_ratio'] <= 100:
            st.success(f"✅ **재무구조 우량**: 부채비율이 `{d['debt_ratio']:.1f}%`로 고금리 국면이나 위기 상황에서도 매우 안전합니다.")
        elif d['debt_ratio'] is not None and d['debt_ratio'] > 200:
            st.warning(f"⚠️ **부채비율 주의**: 부채비율이 `{d['debt_ratio']:.1f}%`로 이자 부담을 점검할 필요가 있습니다.")

        with st.expander("📖 재무건전성 지표 상세 설명"):
            st.markdown("""
            * **부채비율**: 자기자본 대비 총부채 비율입니다. 100% 이하가 이상적이며, 200% 초과 시 금리 상승기 이자 부담이 커집니다.
            * **유동비율**: 1년 안에 현금화할 수 있는 유동자산으로 단기 부채를 갚을 수 있는 능력(100% 이상 권장)을 나타냅니다.
            """)

    # ==========================================
    # TAB 4: 수급 동향
    # ==========================================
    with tab4:
        st.markdown("#### 최근 10영업일 투자자별 순매수 동향 (단위: 억원)")
        if d["investor_list"]:
            df_inv = pd.DataFrame(d["investor_list"]).set_index("날짜")
            sum_f = df_inv["외국인(억원)"].sum()
            sum_i = df_inv["기관(억원)"].sum()
            sum_a = df_inv["개인(억원)"].sum()

            sq1, sq2, sq3 = st.columns(3)
            sq1.metric("10일간 외국인 순매수", f"{sum_f:+,.1f} 억원")
            sq2.metric("10일간 기관 순매수", f"{sum_i:+,.1f} 억원")
            sq3.metric("10일간 개인 순매수", f"{sum_a:+,.1f} 억원")

            if sum_f > 0 and sum_i > 0:
                st.success("🔥 **외인·기관 쌍끌이 순매수**: 메이저 주체들이 동반 매수하여 수급 모멘텀이 매우 우수합니다.")
            elif sum_f < 0 and sum_i < 0:
                st.error("🌧️ **외인·기관 동반 순매도**: 수급 유출이 지속되어 단기 보수적 접근이 권장됩니다.")
            elif sum_f > 0:
                st.info("💡 **외국인 주도 순매수**: 외국인 중심의 순매수가 주가를 지탱하고 있습니다.")
            elif sum_i > 0:
                st.info("💡 **기관 주도 순매수**: 국내 기관 중심의 매수세가 유입 중입니다.")

            st.bar_chart(df_inv[["외국인(억원)", "기관(억원)"]])
            st.dataframe(df_inv, use_container_width=True)
        else:
            st.info("💡 **안내**: 미국 클라우드 서버(Streamlit US) 환경에서는 국내 거래소 보안 방화벽으로 인해 수급 차트 조회가 일시 지연될 수 있습니다.")
            st.link_button(
                f"🔗 {d['name']} 실시간 외인/기관 수급 바로보기 (네이버 증권)",
                f"https://finance.naver.com/item/frgn.naver?code={d['code']}",
                type="primary"
            )
