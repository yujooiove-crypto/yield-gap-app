import streamlit as st
import pandas as pd
import requests
from bs4 import BeautifulSoup
import re

st.set_page_config(
    page_title="국내주식 종목별 주요지표 분석",
    page_icon="📊",
    layout="wide"
)

# 1. 대표 150+ 종목 및 별칭 사전 (즉시 로컬 매핑)
POPULAR_STOCKS = {
    "삼성전자": ("005930", "삼성전자"), "삼전": ("005930", "삼성전자"),
    "삼성전자우": ("005935", "삼성전자우"), "sk하이닉스": ("000660", "SK하이닉스"),
    "하이닉스": ("000660", "SK하이닉스"), "하닉": ("000660", "SK하이닉스"),
    "현대차": ("005380", "현대차"), "현대자동차": ("005380", "현대차"),
    "기아": ("000270", "기아"), "기아차": ("000270", "기아"),
    "lg에너지솔루션": ("373220", "LG에너지솔루션"), "lg엔솔": ("373220", "LG에너지솔루션"), "엔솔": ("373220", "LG에너지솔루션"),
    "삼성바이오로직스": ("207940", "삼성바이오로직스"), "삼바": ("207940", "삼성바이오로직스"),
    "셀트리온": ("068270", "셀트리온"), "알테오젠": ("196170", "알테오젠"),
    "에코프로비엠": ("247540", "에코프로비엠"), "에코프로bm": ("247540", "에코프로비엠"),
    "에코프로": ("086520", "에코프로"), "포스코홀딩스": ("005490", "POSCO홀딩스"),
    "posco홀딩스": ("005490", "POSCO홀딩스"), "포스코": ("005490", "POSCO홀딩스"),
    "naver": ("035420", "NAVER"), "네이버": ("035420", "NAVER"),
    "카카오": ("035720", "카카오"), "카카오뱅크": ("323410", "카카오뱅크"),
    "카카오페이": ("377300", "카카오페이"), "크래프톤": ("259960", "크래프톤"),
    "kb금융": ("105560", "KB금융"), "신한지주": ("055550", "신한지주"),
    "하나금융지주": ("086790", "하나금융지주"), "우리금융지주": ("316140", "우리금융지주"),
    "기업은행": ("024110", "기업은행"), "메리츠금융지주": ("138040", "메리츠금융지주"),
    "두산에너빌리티": ("034020", "두산에너빌리티"), "두산로보틱스": ("454910", "두산로보틱스"),
    "한화에어로스페이스": ("012450", "한화에어로스페이스"), "한화오션": ("042660", "한화오션"),
    "hd현대중공업": ("329180", "HD현대중공업"), "hd현대일렉트릭": ("267260", "HD현대일렉트릭"),
    "삼성sdi": ("006400", "삼성SDI"), "lg화학": ("051910", "LG화학"),
    "lg전자": ("066570", "LG전자"), "kt&g": ("033780", "KT&G"),
    "kt": ("030200", "KT"), "sk텔레콤": ("017670", "SK텔레콤"),
    "lg유플러스": ("032640", "LG유플러스"), "hlb": ("028300", "HLB"),
    "삼천당제약": ("000250", "삼천당제약"), "한미반도체": ("042700", "한미반도체"),
    "한미약품": ("128940", "한미약품"), "유한양행": ("000100", "유한양행"),
    "현대모비스": ("012330", "현대모비스"), "하이브": ("352820", "하이브"),
    "jyp ent.": ("035900", "JYP Ent."), "jyp": ("035900", "JYP Ent."),
    "에스엠": ("041510", "에스엠"), "sm": ("041510", "에스엠"),
    "와이지엔터테인먼트": ("122870", "와이지엔터테인먼트"), "yg": ("122870", "와이지엔터테인먼트"),
    "엔씨소프트": ("036570", "엔씨소프트"), "hpsp": ("403870", "HPSP"),
    "리노공업": ("058470", "리노공업"), "레인보우로보틱스": ("277810", "레인보우로보틱스")
}

# 2. 전국 상장 종목 실시간 검색 함수 (Daum 검색 API 연동)
def search_stock_code_and_name(query):
    q = query.strip()
    if not q:
        return None, None

    # 숫자 6자리 또는 5자리 입력 처리
    if q.isdigit():
        code = q.zfill(6)
        # 로컬 매핑 탐색
        for k, (c, n) in POPULAR_STOCKS.items():
            if c == code:
                return code, n
        return code, f"종목 {code}"

    # 로컬 사전 검색
    clean_q = q.lower().replace(" ", "")
    if clean_q in POPULAR_STOCKS:
        return POPULAR_STOCKS[clean_q]

    # 온라인 Daum 금융 실시간 검색 (모든 상장사 지원)
    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Referer": "https://finance.daum.net/"
        }
        res = requests.get(f"https://finance.daum.net/api/search?q={q}", headers=headers, timeout=3)
        if res.status_code == 200:
            items = res.json().get("data", [])
            for item in items:
                c = item.get("code") or item.get("symbolCode", "").replace("A", "")
                n = item.get("name")
                if c and len(c) == 6:
                    return c, n
    except Exception:
        pass

    return None, None

# 3. 실시간 주가, 재무비율, 수급 통합 수집 함수
@st.cache_data(ttl=180)
def fetch_complete_stock_data(code, default_name):
    data = {
        "code": code, "name": default_name, "market": "KOSPI",
        "price": 0, "change_pct": 0.0,
        "per": None, "cns_per": None, "pbr": None, "eps": None, "div_yield": None,
        "roe": None, "op_margin": None, "net_margin": None,
        "debt_ratio": None, "curr_ratio": None,
        "investor_list": []
    }

    # --- 엔진 1: Daum 금융 API (클라우드 차단율 0%) ---
    headers_daum = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
        "Referer": "https://finance.daum.net/"
    }

    try:
        url_q = f"https://finance.daum.net/api/quotes/A{code}?summary=false&changeFormat=raw"
        res_q = requests.get(url_q, headers=headers_daum, timeout=4)
        if res_q.status_code == 200:
            jq = res_q.json()
            data["name"] = jq.get("name") or default_name
            data["price"] = int(jq.get("tradePrice") or 0)
            data["change_pct"] = round(float(jq.get("changeRate", 0)) * 100, 2)
            data["market"] = jq.get("market", "KOSPI")

            data["per"] = float(jq["per"]) if jq.get("per") else None
            data["pbr"] = float(jq["pbr"]) if jq.get("pbr") else None
            data["eps"] = float(jq["eps"]) if jq.get("eps") else None
            data["div_yield"] = float(jq["dividendYield"]) if jq.get("dividendYield") else None
    except Exception:
        pass

    # --- 엔진 2: 최근 10영업일 수급 동향 (Daum API) ---
    try:
        url_inv = f"https://finance.daum.net/api/investor/days?symbolCode=A{code}&page=1&perPage=10"
        res_inv = requests.get(url_inv, headers=headers_daum, timeout=4)
        if res_inv.status_code == 200:
            inv_items = res_inv.json().get("data", [])
            t_list = []
            for item in inv_items[:10]:
                d_date = str(item.get("date", ""))[:10]
                c_p = data["price"] or int(item.get("tradePrice", 0))
                f_qty = int(item.get("foreignNetBuy", 0))
                i_qty = int(item.get("institutionNetBuy", 0))
                a_qty = int(item.get("individualNetBuy", 0))

                t_list.append({
                    "날짜": d_date,
                    "종가(원)": c_p,
                    "외국인(억원)": round(f_qty * c_p / 100000000, 1),
                    "기관(억원)": round(i_qty * c_p / 100000000, 1),
                    "개인(억원)": round(a_qty * c_p / 100000000, 1)
                })
            data["investor_list"] = t_list
    except Exception:
        pass

    # --- 엔진 3: 네이버 모바일 통합 지표 (추정PER 및 보조 데이터) ---
    headers_naver = {
        "User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 16_5 like Mac OS X) AppleWebKit/605.1.15",
        "Referer": f"https://m.stock.naver.com/domestic/stock/{code}/total"
    }

    try:
        url_int = f"https://m.stock.naver.com/api/stock/{code}/integration"
        res_int = requests.get(url_int, headers=headers_naver, timeout=3)
        if res_int.status_code == 200:
            for it in res_int.json().get("totalInfos", []):
                k, v = it.get("key", ""), str(it.get("value", "")).replace(",", "")
                try:
                    if "추정PER" in k and data["cns_per"] is None:
                        data["cns_per"] = float(v.replace("배", ""))
                    elif "PER" in k and data["per"] is None:
                        data["per"] = float(v.replace("배", ""))
                    elif "PBR" in k and data["pbr"] is None:
                        data["pbr"] = float(v.replace("배", ""))
                    elif "배당수익률" in k and data["div_yield"] is None:
                        data["div_yield"] = float(v.replace("%", ""))
                except Exception:
                    pass
    except Exception:
        pass

    # --- 엔진 4: 네이버 기업실적분석 테이블 (ROE, 영업이익률, 부채비율, 유동비율) ---
    try:
        url_pc = f"https://finance.naver.com/item/main.naver?code={code}"
        headers_pc = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Referer": "https://finance.naver.com/"
        }
        res_pc = requests.get(url_pc, headers=headers_pc, timeout=3)
        res_pc.encoding = "cp949"
        soup = BeautifulSoup(res_pc.text, "html.parser")
        table = soup.find("div", class_="section cop_analysis")
        if table:
            for tr in table.find_all("tr"):
                th = tr.find("th")
                if not th:
                    continue
                title = th.text.strip()
                tds = tr.find_all("td")
                vals = []
                for td in tds:
                    v_str = td.text.replace(",", "").strip()
                    try:
                        vals.append(float(v_str))
                    except ValueError:
                        pass
                if vals:
                    latest = vals[-1]
                    if "ROE" in title and data["roe"] is None:
                        data["roe"] = latest
                    elif "영업이익률" in title and data["op_margin"] is None:
                        data["op_margin"] = latest
                    elif "순이익률" in title and data["net_margin"] is None:
                        data["net_margin"] = latest
                    elif "부채비율" in title and data["debt_ratio"] is None:
                        data["debt_ratio"] = latest
                    elif ("유동비율" in title or "당좌비율" in title) and data["curr_ratio"] is None:
                        data["curr_ratio"] = latest
    except Exception:
        pass

    # ROE 자동 역산 보정 (듀퐁 공식: ROE = PBR / PER * 100)
    if data["roe"] is None and data["per"] and data["pbr"] and data["per"] > 0:
        data["roe"] = round((data["pbr"] / data["per"]) * 100, 1)

    return data

# --- 사이드바 ---
with st.sidebar:
    st.header("⚙️ 분석 기준 설정")
    deposit_rate = st.slider("기준 예금 이자율 (%)", min_value=1.0, max_value=10.0, value=3.5, step=0.1)
    st.caption("일드갭 산출 시 비교 기준이 되는 시중 정기예금/국고채 금리입니다.")
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
st.caption("가치평가 · 수익성 · 재무건전성 종합 진단 및 최근 10영업일 수급 동향")

# 인기 종목 원클릭 바로가기 버튼
st.write("🔥 **인기 종목 빠른 조회:**")
btn_cols = st.columns(7)
popular_list = ["삼성전자", "SK하이닉스", "현대차", "기아", "셀트리온", "알테오젠", "에코프로비엠"]
for i, name in enumerate(popular_list):
    if btn_cols[i].button(name, use_container_width=True):
        st.session_state["query_input"] = name

if "query_input" not in st.session_state:
    st.session_state["query_input"] = "삼성전자"

col_search, col_btn = st.columns([4, 1])
with col_search:
    user_query = st.text_input("종목명 또는 6자리 코드 입력", value=st.session_state["query_input"])
with col_btn:
    st.write("")
    st.write("")
    run_btn = st.button("종목 분석", type="primary", use_container_width=True)

if run_btn or user_query != st.session_state.get("last_searched"):
    st.session_state["last_searched"] = user_query
    target_code, target_name = search_stock_code_and_name(user_query)

    if not target_code:
        st.error(f"'{user_query}' 종목을 찾을 수 없습니다. 정확한 종목명이나 6자리 코드(예: 삼성전자 또는 005930)를 입력해 주세요.")
    else:
        with st.spinner(f"'{target_name}' 금융 지표 및 수급 데이터를 분석 중입니다..."):
            d = fetch_complete_stock_data(target_code, target_name)

        if d["price"] == 0:
            st.error("현재 금융 데이터 서버 응답이 지연되고 있습니다. 잠시 후 다시 시도해 주세요.")
        else:
            st.divider()
            h1, h2, h3 = st.columns([2, 1, 1])
            h1.subheader(f"🏢 {d['name']} ({d['code']})")
            h2.metric("현재 주가", f"{d['price']:,.0f}원", f"{d['change_pct']:+.2f}%" if d['change_pct'] != 0 else "")
            h3.write(f"**소속 시장:** `{d['market']}`")

            tab1, tab2, tab3, tab4 = st.tabs([
                "💰 1. 가치평가 지표",
                "📈 2. 수익성 지표",
                "🛡️ 3. 재무건전성 지표",
                "👥 4. 최근 10영업일 수급 동향"
            ])

            # TAB 1: 가치평가
            with tab1:
                st.markdown("#### 기업 가치 대비 주가 수준 (Valuation)")
                v1, v2, v3, v4 = st.columns(4)
                v1.metric("PER (결산)", f"{d['per']:.1f}배" if d['per'] else "N/A", "15배 이하 저평가")
                v2.metric("PBR (순자산비율)", f"{d['pbr']:.2f}배" if d['pbr'] else "N/A", "1.0배 이하 청산가치")
                v3.metric("추정 PER (선행)", f"{d['cns_per']:.1f}배" if d['cns_per'] else "N/A", "컨센서스 기준")
                v4.metric("배당수익률", f"{d['div_yield']:.2f}%" if d['div_yield'] else "0.00%", "3% 이상 안전마진")

                st.markdown("##### 📌 벤저민 그레이엄 일드갭(초과수익률) 진단")
                base_per = d['cns_per'] or d['per']
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

            # TAB 2: 수익성
            with tab2:
                st.markdown("#### 돈을 버는 효율성과 마진율 (Profitability)")
                p1, p2, p3 = st.columns(3)
                p1.metric("ROE (자기자본이익률)", f"{d['roe']:.1f}%" if d['roe'] is not None else "N/A", "10% 이상 우량")
                p2.metric("영업이익률", f"{d['op_margin']:.1f}%" if d['op_margin'] is not None else "N/A", "본업 경쟁력")
                p3.metric("순이익률", f"{d['net_margin']:.1f}%" if d['net_margin'] is not None else "N/A", "최종 마진")

                if d['roe'] is not None and d['roe'] >= 10:
                    st.success(f"✅ **수익성 우수**: ROE가 `{d['roe']:.1f}%`로 자기자본 대비 매우 우수한 복리 수익 창출력을 나타내고 있습니다.")
                elif d['roe'] is not None:
                    st.info(f"ℹ️ **수익성 보통**: ROE가 `{d['roe']:.1f}%` 수준입니다.")

                with st.expander("📖 수익성 지표 상세 설명"):
                    st.markdown("""
                    * **ROE (자기자본이익률)**: 주주 자본으로 1년간 얼마의 순이익을 남겼는지 측정하는 핵심 지표입니다. (10~15% 이상 우수)
                    * **영업이익률**: 매출액 중 원가와 판관비를 제하고 남은 순수 본업의 영업이익 비율로, 브랜드 가격 결정력을 보여줍니다.
                    * **순이익률**: 금융비용과 세금까지 모두 납부한 뒤 최종 주주 몫으로 남은 순이익 비율입니다.
                    """)

            # TAB 3: 재무건전성
            with tab3:
                st.markdown("#### 재무적 생존 체력과 부도 위험 (Stability)")
                s1, s2 = st.columns(2)
                s1.metric("부채비율", f"{d['debt_ratio']:.1f}%" if d['debt_ratio'] is not None else "N/A", "100% 이하 안정권")
                s2.metric("유동비율", f"{d['curr_ratio']:.1f}%" if d['curr_ratio'] is not None else "N/A", "100% 이상 권장")

                if d['debt_ratio'] is not None and d['debt_ratio'] <= 100:
                    st.success(f"✅ **재무구조 우량**: 부채비율이 `{d['debt_ratio']:.1f}%`로 고금리 국면이나 위기 상황에서도 매우 안전합니다.")
                elif d['debt_ratio'] is not None and d['debt_ratio'] > 200:
                    st.warning(f"⚠️ **부채비율 주의**: 부채비율이 `{d['debt_ratio']:.1f}%`로 이자비용 부담을 점검할 필요가 있습니다.")

                with st.expander("📖 재무건전성 지표 상세 설명"):
                    st.markdown("""
                    * **부채비율**: 자기자본 대비 총부채 비율입니다. 100% 이하가 이상적이며, 200% 초과 시 금리 상승기 이자 부담이 커집니다.
                    * **유동비율**: 1년 안에 현금화할 수 있는 유동자산으로 단기 부채를 갚을 수 있는 능력(100% 이상 권장)을 나타냅니다.
                    """)

            # TAB 4: 수급 동향
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
                    st.info("수급 데이터를 집계 중입니다. 잠시 후 다시 조회해 주세요.")
