import streamlit as st
import pandas as pd
import requests
import re
from datetime import datetime

st.set_page_config(
    page_title="국내주식 종목별 주요지표 분석",
    page_icon="📊",
    layout="wide"
)

# 대표 주요 종목 사전 (한글 종목명 즉시 매핑)
STOCK_DICT = {
    "삼성전자": "005930", "sk하이닉스": "000660", "현대차": "005380", "기아": "000270",
    "lg에너지솔루션": "373220", "삼성바이오로직스": "207940", "셀트리온": "068270",
    "kb금융": "105560", "신한지주": "055550", "포스코홀딩스": "005490", "posco홀딩스": "005490",
    "naver": "035420", "네이버": "035420", "카카오": "035720", "에코프로비엠": "247540",
    "에코프로": "086520", "알테오젠": "196170", "hlb": "028300", "삼천당제약": "000250",
    "한미반도체": "042700", "두산에너빌리티": "034020", "한화에어로스페이스": "012450",
    "크래프톤": "259960", "카카오뱅크": "323410", "lg전자": "066570", "현대모비스": "012330",
    "삼성sdi": "006400", "lg화학": "051910", "kt&g": "033780", "하나금융지주": "086790"
}

def get_code(query):
    q = query.strip()
    if q.isdigit() and len(q) == 6:
        return q
    clean_q = q.lower().replace(" ", "")
    return STOCK_DICT.get(clean_q)

# 1. 에프앤가이드(FnGuide) 공식 재무비율 직통 수집 함수
def fetch_fnguide_financials(code):
    ratios = {
        "roe": None, "op_margin": None, "net_margin": None,
        "debt_ratio": None, "curr_ratio": None
    }
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8"
    }

    try:
        # FnGuide 재무비율 전용 페이지 (수익성, 안정성, 성장성 비율 집약)
        url_ratio = f"https://comp.fnguide.com/SVO2/ASP/SVD_FinanceRatio.asp?pGB=1&gicode=A{code}"
        res = requests.get(url_ratio, headers=headers, timeout=5)
        if res.status_code == 200:
            rows = re.findall(r'<tr[^>]*>(.*?)</tr>', res.text, re.DOTALL)
            for r in rows:
                th_m = re.search(r'<th[^>]*>(.*?)</th>', r, re.DOTALL)
                if not th_m:
                    continue
                title = re.sub(r'<.*?>', '', th_m.group(1)).replace(" ", "").strip()

                td_ms = re.findall(r'<td[^>]*>(.*?)</td>', r, re.DOTALL)
                vals = []
                for td in td_ms:
                    c_v = re.sub(r'<.*?>', '', td).replace(',', '').replace('%', '').strip()
                    try:
                        vals.append(float(c_v))
                    except ValueError:
                        pass

                if not vals:
                    continue
                latest = vals[-1]  # 가장 최근 확정 결산치

                if "ROE" in title and ratios["roe"] is None:
                    ratios["roe"] = latest
                elif "영업이익률" in title and ratios["op_margin"] is None:
                    ratios["op_margin"] = latest
                elif "순이익률" in title and ratios["net_margin"] is None:
                    ratios["net_margin"] = latest
                elif "부채비율" in title and ratios["debt_ratio"] is None:
                    ratios["debt_ratio"] = latest
                elif "유동비율" in title and ratios["curr_ratio"] is None:
                    ratios["curr_ratio"] = latest

        # 만약 미반영 항목이 있으면 FnGuide 메인 하이라이트에서 2차 보강
        if ratios["roe"] is None or ratios["debt_ratio"] is None:
            url_main = f"https://comp.fnguide.com/SVO2/ASP/SVD_Main.asp?pGB=1&gicode=A{code}"
            res_m = requests.get(url_main, headers=headers, timeout=5)
            if res_m.status_code == 200:
                m_rows = re.findall(r'<tr[^>]*>(.*?)</tr>', res_m.text, re.DOTALL)
                for r in m_rows:
                    th_m = re.search(r'<th[^>]*>(.*?)</th>', r, re.DOTALL)
                    if not th_m:
                        continue
                    t = re.sub(r'<.*?>', '', th_m.group(1)).replace(" ", "").strip()
                    td_ms = re.findall(r'<td[^>]*>(.*?)</td>', r, re.DOTALL)
                    vals = []
                    for td in td_ms:
                        c_v = re.sub(r'<.*?>', '', td).replace(',', '').replace('%', '').strip()
                        try:
                            vals.append(float(c_v))
                        except ValueError:
                            pass
                    if vals:
                        latest = vals[-1]
                        if "ROE" in t and ratios["roe"] is None:
                            ratios["roe"] = latest
                        elif "영업이익률" in t and ratios["op_margin"] is None:
                            ratios["op_margin"] = latest
                        elif "순이익률" in t and ratios["net_margin"] is None:
                            ratios["net_margin"] = latest
                        elif "부채비율" in t and ratios["debt_ratio"] is None:
                            ratios["debt_ratio"] = latest
    except Exception:
        pass

    return ratios

# 2. 통합 종목 데이터 수집 함수
@st.cache_data(ttl=300)
def fetch_stock_all(code):
    data = {
        "name": code, "code": code, "price": 0, "change_pct": 0.0,
        "per": None, "cns_per": None, "pbr": None, "eps": None, "div_yield": None,
        "roe": None, "op_margin": None, "net_margin": None,
        "debt_ratio": None, "curr_ratio": None,
        "investor_list": []
    }

    headers = {
        "User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 16_5 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.5 Mobile/15E148 Safari/604.1",
        "Referer": f"https://m.stock.naver.com/domestic/stock/{code}/total"
    }

    # 1) 현재가 및 기본 시세 (네이버 모바일 API)
    try:
        r_basic = requests.get(f"https://m.stock.naver.com/api/stock/{code}/basic", headers=headers, timeout=4)
        if r_basic.status_code == 200:
            jb = r_basic.json()
            data["name"] = jb.get("stockName", code)
            data["price"] = int(str(jb.get("closePrice", "0")).replace(",", ""))
            data["change_pct"] = float(str(jb.get("fluctuationsRatio", "0")).replace("%", "").strip())
    except Exception:
        pass

    # 2) 밸류에이션 지표 (PER, PBR, 추정PER, 배당수익률, EPS)
    try:
        r_int = requests.get(f"https://m.stock.naver.com/api/stock/{code}/integration", headers=headers, timeout=4)
        if r_int.status_code == 200:
            for item in r_int.json().get("totalInfos", []):
                k, v = item.get("key", ""), str(item.get("value", "")).replace(",", "")
                try:
                    if k == "PER" and data["per"] is None:
                        data["per"] = float(v.replace("배", ""))
                    elif k == "PBR" and data["pbr"] is None:
                        data["pbr"] = float(v.replace("배", ""))
                    elif k == "추정PER" and data["cns_per"] is None:
                        data["cns_per"] = float(v.replace("배", ""))
                    elif k == "배당수익률" and data["div_yield"] is None:
                        data["div_yield"] = float(v.replace("%", ""))
                    elif k == "EPS" and data["eps"] is None:
                        data["eps"] = float(v.replace("원", ""))
                except Exception:
                    pass
    except Exception:
        pass

    # 3) 수익성 및 재무건전성 지표 (FnGuide 원천 DB 실시간 동기화)
    fn_ratios = fetch_fnguide_financials(code)
    data["roe"] = fn_ratios["roe"]
    data["op_margin"] = fn_ratios["op_margin"]
    data["net_margin"] = fn_ratios["net_margin"]
    data["debt_ratio"] = fn_ratios["debt_ratio"]
    data["curr_ratio"] = fn_ratios["curr_ratio"]

    # ROE 결측 시 자본효율 공식(PBR/PER)으로 자동 보정
    if data["roe"] is None and data["per"] and data["pbr"] and data["per"] > 0:
        data["roe"] = round((data["pbr"] / data["per"]) * 100, 1)

    # 4) 최근 10영업일 수급 동향 (네이버 수급 -> Daum 수급 이중 백업)
    try:
        r_trend = requests.get(f"https://m.stock.naver.com/api/stock/{code}/trend?pageSize=10&page=1", headers=headers, timeout=4)
        if r_trend.status_code == 200:
            jt = r_trend.json()
            rows = jt if isinstance(jt, list) else (jt.get("message") or jt.get("result") or jt.get("items") or [])
            t_list = []
            for row in rows[:10]:
                dt_raw = str(row.get("bizdate") or row.get("date") or "")
                c_p = int(str(row.get("closePrice") or data["price"] or 0).replace(",", ""))
                frg_q = int(str(row.get("foreignerPureBuyQuant") or row.get("foreignerNetBuy") or 0).replace(",", ""))
                inst_q = int(str(row.get("organPureBuyQuant") or row.get("institutionNetBuy") or 0).replace(",", ""))
                ant_q = int(str(row.get("individualPureBuyQuant") or row.get("individualNetBuy") or 0).replace(",", ""))

                dt_fmt = f"{dt_raw[:4]}-{dt_raw[4:6]}-{dt_raw[6:]}" if len(dt_raw) == 8 else dt_raw
                t_list.append({
                    "날짜": dt_fmt,
                    "종가(원)": c_p,
                    "외국인(억원)": round(frg_q * c_p / 100000000, 1),
                    "기관(억원)": round(inst_q * c_p / 100000000, 1),
                    "개인(억원)": round(ant_q * c_p / 100000000, 1)
                })
            data["investor_list"] = t_list
    except Exception:
        pass

    if not data["investor_list"]:
        try:
            d_headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                "Referer": f"https://finance.daum.net/quotes/A{code}"
            }
            d_res = requests.get(f"https://finance.daum.net/api/investor/days?symbolCode=A{code}&page=1&perPage=10", headers=d_headers, timeout=3)
            if d_res.status_code == 200:
                d_list = []
                for it in d_res.json().get("data", [])[:10]:
                    d_date = it.get("date", "")[:10]
                    c_p = data["price"]
                    f_b = it.get("foreignNetBuy", 0)
                    i_b = it.get("institutionNetBuy", 0)
                    a_b = it.get("individualNetBuy", 0)
                    d_list.append({
                        "날짜": d_date,
                        "종가(원)": c_p,
                        "외국인(억원)": round(f_b * c_p / 100000000, 1),
                        "기관(억원)": round(i_b * c_p / 100000000, 1),
                        "개인(억원)": round(a_b * c_p / 100000000, 1)
                    })
                data["investor_list"] = d_list
        except Exception:
            pass

    return data

# --- 사이드바 ---
with st.sidebar:
    st.header("⚙️ 분석 기준 설정")
    deposit_rate = st.slider("기준 예금 이자율 (%)", min_value=1.0, max_value=10.0, value=3.5, step=0.1)
    st.caption("일드갭 산출 시 비교 기준이 되는 시중 정기예금/국고채 금리입니다.")
    st.divider()
    st.markdown("""
    **📖 일드갭(초과수익률) 판정 기준**
    - **+4.0%p 이상**: 매우 유리 (적극 매수)
    - **+2.0%p ~ +4.0%p**: 유리 (비중 확대)
    - **+1.0%p ~ +2.0%p**: 다소 유리 (선별 투자)
    - **0.0%p ~ +1.0%p**: 메리트 없음
    - **0.0%p 미만**: 매우 불리 (예금 보유)
    """)

# --- 메인 화면 ---
st.title("📈 국내주식 종목별 주요지표 분석")
st.caption("가치평가 · 수익성 · 재무건전성 종합 진단 및 최근 10영업일 외인/기관 수급 추이")

c_in, c_btn = st.columns([4, 1])
with c_in:
    stock_input = st.text_input("종목명 또는 6자리 코드 입력", value="삼성전자", placeholder="예: 삼성전자, SK하이닉스, 현대차, 005930")
with c_btn:
    st.write("")
    st.write("")
    btn = st.button("종목 분석", type="primary", use_container_width=True)

if btn or "analyzed_target" in st.session_state:
    if btn:
        target_code = get_code(stock_input)
        if not target_code:
            st.warning(f"'{stock_input}' 종목을 찾을 수 없습니다. 6자리 종목코드(예: 삼성전자 005930)를 입력해 주세요.")
            st.stop()
        st.session_state["analyzed_target"] = target_code
    else:
        target_code = st.session_state["analyzed_target"]

    with st.spinner("FnGuide 및 거래소 금융 데이터 분석 중..."):
        d = fetch_stock_all(target_code)

    if d["price"] == 0:
        st.error("현재 일시적인 네트워크 지연으로 시세를 불러오지 못했습니다. 잠시 후 다시 시도해 주세요.")
        st.stop()

    st.divider()
    h1, h2 = st.columns([3, 1])
    h1.subheader(f"🏢 {d['name']} ({d['code']})")
    h2.metric("현재 주가", f"{d['price']:,.0f}원", f"{d['change_pct']:+.2f}%" if d['change_pct'] != 0 else "")

    tab1, tab2, tab3, tab4 = st.tabs([
        "💰 1. 가치평가 지표",
        "📈 2. 수익성 지표",
        "🛡️ 3. 재무건전성 지표",
        "👥 4. 최근 10영업일 수급 동향"
    ])

    # 1. 가치평가
    with tab1:
        st.markdown("#### 기업 가치 대비 주가 수준 (Valuation)")
        v1, v2, v3, v4 = st.columns(4)
        v1.metric("PER (결산)", f"{d['per']:.1f}배" if d['per'] is not None else "N/A", "15배 이하 저평가")
        v2.metric("PBR (순자산비율)", f"{d['pbr']:.2f}배" if d['pbr'] is not None else "N/A", "1.0배 이하 청산가치")
        v3.metric("추정 PER (선행)", f"{d['cns_per']:.1f}배" if d['cns_per'] is not None else "N/A", "컨센서스 기준")
        v4.metric("배당수익률", f"{d['div_yield']:.2f}%" if d['div_yield'] is not None else "0.00%", "3% 이상 안전마진")

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
                st.warning("🟡 **다소 유리 (선별 투자)** — 예금 대비 1~2%p 초과수익 구간으로 개별 종목의 펀더멘털 선별이 필요합니다.")
            elif yield_gap >= 0.0:
                st.warning("🟠 **메리트 없음 (분산 권장)** — 주식 위험 대비 보상이 적어 예금·채권 병행이 유리합니다.")
            else:
                st.error("🔴 **매우 불리 (예금 보유 유리)** — 주식 기대수익률이 무위험 예금 금리보다 낮아 확정금리 자산이 유리합니다.")
        else:
            st.info("적자 기업이거나 PER 데이터가 없어 일드갭 계산을 생략합니다.")

        with st.expander("📖 가치평가 지표 상세 설명"):
            st.markdown("""
            * **PER (주가수익비율)**: 주가를 1주당 순이익(EPS)으로 나눈 값으로, 낮을수록 벌어들이는 이익 대비 주가가 저렴함을 뜻합니다.
            * **PBR (주가순자산비율)**: 주가를 1주당 순자산(BPS)으로 나눈 값으로, 1.0배 미만이면 회사 순자산 청산가치보다 싼 가격입니다.
            * **일드갭 (Yield Gap)**: 주식 기대수익률(1/PER)에서 예금/국채 금리를 뺀 초과수익률로, 안전자산 대비 주식의 초과 보상을 측정합니다.
            """)

    # 2. 수익성
    with tab2:
        st.markdown("#### 돈을 버는 효율성과 마진율 (Profitability)")
        p1, p2, p3 = st.columns(3)
        p1.metric("ROE (자기자본이익률)", f"{d['roe']:.1f}%" if d['roe'] is not None else "N/A", "10% 이상 우량")
        p2.metric("영업이익률", f"{d['op_margin']:.1f}%" if d['op_margin'] is not None else "N/A", "본업 경쟁력")
        p3.metric("순이익률", f"{d['net_margin']:.1f}%" if d['net_margin'] is not None else "N/A", "최종 마진")

        if d['roe'] is not None and d['roe'] >= 10:
            st.success(f"✅ **수익성 우수**: ROE가 `{d['roe']:.1f}%`로 자기자본 대비 매우 우수한 복리 수익 창출력을 입증하고 있습니다.")
        elif d['roe'] is not None:
            st.info(f"ℹ️ **수익성 보통**: ROE가 `{d['roe']:.1f}%` 수준입니다.")

        with st.expander("📖 수익성 지표 상세 설명"):
            st.markdown("""
            * **ROE (자기자본이익률)**: 주주 자본으로 1년간 얼마의 순이익을 창출했는지 측정하는 대표 수익성 지표입니다. (10~15% 이상 우수)
            * **영업이익률**: 매출액 중 원가와 판관비를 제하고 남은 순수 본업의 영업이익 비율로, 브랜드 가격 결정력을 증명합니다.
            * **순이익률**: 금융비용과 세금까지 모두 납부한 뒤 최종 주주 몫으로 남은 순이익 비율입니다.
            """)

    # 3. 재무건전성
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
            * **부채비율**: 자기자본 대비 총부채 비율입니다. 100% 이하가 이상적이며, 200%를 초과하면 금리 인상기 이자 부담이 급증할 수 있습니다.
            * **유동비율**: 1년 안에 현금화할 수 있는 유동자산으로 단기 부채를 갚을 수 있는 능력(100% 이상 권장)을 나타냅니다.
            """)

    # 4. 수급 동향
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
                st.success("🔥 **외인·기관 쌍끌이 순매수**: 메이저 수급 주체들이 동반 매수하여 주가 하방 지지력이 매우 강합니다.")
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
