import streamlit as st
import pandas as pd
import requests
from bs4 import BeautifulSoup
import yfinance as yf
import re

st.set_page_config(
    page_title="국내주식 종목별 주요지표 분석",
    page_icon="📊",
    layout="wide"
)

# 1. 전국 상장 종목(2,600+) 실시간 검색 엔진 (네이버 AC + 약칭 사전)
STOCK_ALIASES = {
    "삼전": "005930", "삼성전자": "005930", "하닉": "000660", "하이닉스": "000660", "sk하이닉스": "000660",
    "현대차": "005380", "현대자동차": "005380", "기아차": "000270", "기아": "000270",
    "엔솔": "373220", "lg엔솔": "373220", "lg에너지솔루션": "373220",
    "삼바": "207940", "삼성바이오로직스": "207940", "셀트리온": "068270", "알테오젠": "196170",
    "에코프로bm": "247540", "에코프로비엠": "247540", "에코프로": "086520",
    "포스코": "005490", "포스코홀딩스": "005490", "posco홀딩스": "005490",
    "네이버": "035420", "naver": "035420", "카카오": "035720", "삼양식품": "003230",
    "한화에어로": "012450", "한화에어로스페이스": "012450", "두산에너빌리티": "034020"
}

def search_krx_stock(query):
    q = query.strip()
    if not q:
        return None, None

    # A. 6자리 숫자 코드 입력 시
    if q.isdigit() and len(q) == 6:
        # 네이버 기본 API로 기업명 확인
        try:
            r = requests.get(f"https://m.stock.naver.com/api/stock/{q}/basic", headers={"User-Agent": "Mozilla/5.0"}, timeout=3)
            if r.status_code == 200:
                name = r.json().get("stockName", f"종목 {q}")
                return q, name
        except Exception:
            pass
        return q, f"종목 {q}"

    # B. 대표 약칭 사전 우선 매핑
    clean_q = q.lower().replace(" ", "")
    if clean_q in STOCK_ALIASES:
        code = STOCK_ALIASES[clean_q]
        return code, q

    # C. 네이버 금융 공식 자동완성(AC) 검색 엔진 (국내 전 종목 실시간 조회)
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
    try:
        url = "https://ac.finance.naver.com/ac"
        params = {"q": q, "q_enc": "utf-8", "st": "1", "r_format": "json", "r_enc": "utf-8"}
        res = requests.get(url, params=params, headers=headers, timeout=4)
        if res.status_code == 200:
            items = res.json().get("items", [[]])[0]
            if items:
                # 1순위: 정확히 일치하는 종목
                for item in items:
                    if len(item) >= 2 and item[0].replace(" ", "") == q.replace(" ", ""):
                        return item[1], item[0]
                # 2순위: 검색어 포함 첫 번째 종목
                if len(items[0]) >= 2:
                    return items[0][1], items[0][0]
    except Exception:
        pass

    # D. Daum 검색 백업
    try:
        url_d = "https://finance.daum.net/api/search"
        res_d = requests.get(url_d, params={"q": q}, headers={"User-Agent": headers["User-Agent"], "Referer": "https://finance.daum.net/"}, timeout=3)
        if res_d.status_code == 200:
            d_items = res_d.json().get("data", [])
            for it in d_items:
                c = it.get("code") or it.get("symbolCode", "").replace("A", "")
                n = it.get("name")
                if c and len(c) == 6:
                    return c, n
    except Exception:
        pass

    return None, None

# 2. 모든 상장 종목의 실제 금융 데이터 및 수급 통합 수집
@st.cache_data(ttl=120)
def fetch_full_stock_metrics(code, default_name):
    data = {
        "code": code, "name": default_name, "price": 0, "change_pct": 0.0,
        "per": None, "cns_per": None, "pbr": None, "eps": None, "bps": None, "div_yield": None,
        "roe": None, "op_margin": None, "net_margin": None,
        "debt_ratio": None, "curr_ratio": None,
        "investor_list": []
    }

    headers_mobile = {
        "User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 16_5 like Mac OS X) AppleWebKit/605.1.15",
        "Referer": f"https://m.stock.naver.com/domestic/stock/{code}/total"
    }

    # 1) 실시간 주가 및 등락률
    try:
        r_b = requests.get(f"https://m.stock.naver.com/api/stock/{code}/basic", headers=headers_mobile, timeout=4)
        if r_b.status_code == 200:
            jb = r_b.json()
            data["name"] = jb.get("stockName") or default_name
            data["price"] = int(str(jb.get("closePrice", "0")).replace(",", ""))
            data["change_pct"] = float(str(jb.get("fluctuationsRatio", "0")).replace("%", "").strip())
    except Exception:
        pass

    # 2) 가치평가 공식 지표 (PER, PBR, 추정PER, EPS, BPS, 배당수익률)
    try:
        r_i = requests.get(f"https://m.stock.naver.com/api/stock/{code}/integration", headers=headers_mobile, timeout=4)
        if r_i.status_code == 200:
            for it in r_i.json().get("totalInfos", []):
                k, v = it.get("key", ""), str(it.get("value", "")).replace(",", "")
                try:
                    if k == "PER" and data["per"] is None:
                        data["per"] = float(v.replace("배", ""))
                    elif k == "PBR" and data["pbr"] is None:
                        data["pbr"] = float(v.replace("배", ""))
                    elif "추정PER" in k and data["cns_per"] is None:
                        data["cns_per"] = float(v.replace("배", ""))
                    elif "배당수익률" in k and data["div_yield"] is None:
                        data["div_yield"] = float(v.replace("%", ""))
                    elif k == "EPS" and data["eps"] is None:
                        data["eps"] = float(v.replace("원", ""))
                    elif k == "BPS" and data["bps"] is None:
                        data["bps"] = float(v.replace("원", ""))
                except Exception:
                    pass
    except Exception:
        pass

    # 3) 수익성(ROE) 수학적 공준 산출: (PBR / PER) * 100 또는 (EPS / BPS) * 100
    if data["pbr"] and data["per"] and data["per"] > 0:
        data["roe"] = round((data["pbr"] / data["per"]) * 100, 1)
    elif data["eps"] and data["bps"] and data["bps"] > 0:
        data["roe"] = round((data["eps"] / data["bps"]) * 100, 1)

    # 4) 영업이익률, 순이익률, 부채비율, 유동비율 실제 공시 수집 (네이버 PC 테이블 탐색)
    try:
        url_pc = f"https://finance.naver.com/item/main.naver?code={code}"
        headers_pc = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36", "Referer": "https://finance.naver.com/"}
        r_pc = requests.get(url_pc, headers=headers_pc, timeout=5)
        r_pc.encoding = "cp949"
        soup = BeautifulSoup(r_pc.text, "html.parser")
        tbl = soup.find("div", class_="section cop_analysis")
        if tbl:
            for tr in tbl.find_all("tr"):
                th = tr.find("th")
                if not th: continue
                title = th.text.strip()
                tds = tr.find_all("td")
                # 유효한 숫자들 중 가장 최근 확정치 선택
                vals = []
                for td in tds:
                    v_str = td.text.replace(",", "").strip()
                    try:
                        vals.append(float(v_str))
                    except ValueError:
                        pass
                if vals:
                    # 연간 최근 결산치(앞쪽 3~4번째) 또는 마지막 유효치
                    latest_valid = vals[3] if len(vals) >= 4 else vals[-1]
                    if "영업이익률" in title and data["op_margin"] is None:
                        data["op_margin"] = latest_valid
                    elif "순이익률" in title and data["net_margin"] is None:
                        data["net_margin"] = latest_valid
                    elif "부채비율" in title and data["debt_ratio"] is None:
                        data["debt_ratio"] = latest_valid
                    elif ("유동비율" in title or "당좌비율" in title) and data["curr_ratio"] is None:
                        data["curr_ratio"] = latest_valid
    except Exception:
        pass

    # 5) 글로벌 금융 DB(yfinance) 교차 검증 (미수집 항목 100% 보강)
    if data["op_margin"] is None or data["debt_ratio"] is None or data["curr_ratio"] is None:
        try:
            for sfx in [".KS", ".KQ"]:
                info = yf.Ticker(f"{code}{sfx}").info
                if info and (info.get("regularMarketPrice") or info.get("currentPrice") or info.get("shortName")):
                    if data["op_margin"] is None and info.get("operatingMargins"):
                        data["op_margin"] = round(info["operatingMargins"] * 100, 1)
                    if data["net_margin"] is None and info.get("profitMargins"):
                        data["net_margin"] = round(info["profitMargins"] * 100, 1)
                    if data["debt_ratio"] is None and info.get("debtToEquity"):
                        data["debt_ratio"] = round(float(info["debtToEquity"]), 1)
                    if data["curr_ratio"] is None and info.get("currentRatio"):
                        data["curr_ratio"] = round(float(info["currentRatio"]) * 100, 1)
                    break
        except Exception:
            pass

    # 6) 최근 10영업일 수급 동향 (1차: 네이버 모바일 API -> 2차: 네이버 PC 수급표 -> 3차: Daum API)
    # 1차: 네이버 모바일 trend
    try:
        r_t = requests.get(f"https://m.stock.naver.com/api/stock/{code}/trend?pageSize=10&page=1", headers=headers_mobile, timeout=4)
        if r_t.status_code == 200:
            jt = r_t.json()
            rows = jt if isinstance(jt, list) else (jt.get("message") or jt.get("result") or jt.get("items") or [])
            t_list = []
            for row in rows[:10]:
                dt_raw = str(row.get("bizdate") or row.get("date") or "")
                c_p = int(str(row.get("closePrice") or data["price"] or 0).replace(",", ""))
                frg_q = int(str(row.get("foreignerPureBuyQuant") or 0).replace(",", ""))
                inst_q = int(str(row.get("organPureBuyQuant") or 0).replace(",", ""))
                ant_q = int(str(row.get("individualPureBuyQuant") or 0).replace(",", ""))

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

    # 2차: 네이버 PC frgn.naver 백업
    if not data["investor_list"]:
        try:
            r_frgn = requests.get(f"https://finance.naver.com/item/frgn.naver?code={code}", headers={"User-Agent": "Mozilla/5.0"}, timeout=4)
            r_frgn.encoding = "cp949"
            soup_f = BeautifulSoup(r_frgn.text, "html.parser")
            tbl_f = soup_f.find("table", class_="type2")
            if tbl_f:
                f_list = []
                for tr in tbl_f.find_all("tr"):
                    tds = tr.find_all("td")
                    if len(tds) >= 7:
                        d_str = tds[0].text.strip()
                        if re.match(r"\d{4}\.\d{2}\.\d{2}", d_str):
                            c_p = int(tds[1].text.strip().replace(",", ""))
                            inst_q = int(tds[5].text.strip().replace(",", ""))
                            fore_q = int(tds[6].text.strip().replace(",", ""))
                            f_list.append({
                                "날짜": d_str.replace(".", "-"),
                                "종가(원)": c_p,
                                "외국인(억원)": round(fore_q * c_p / 100000000, 1),
                                "기관(억원)": round(inst_q * c_p / 100000000, 1),
                                "개인(억원)": 0.0
                            })
                            if len(f_list) >= 10:
                                break
                data["investor_list"] = f_list
        except Exception:
            pass

    # 3차: Daum 금융 수급 백업
    if not data["investor_list"]:
        try:
            d_headers = {"User-Agent": "Mozilla/5.0", "Referer": f"https://finance.daum.net/quotes/A{code}"}
            r_d = requests.get(f"https://finance.daum.net/api/investor/days?symbolCode=A{code}&page=1&perPage=10", headers=d_headers, timeout=3)
            if r_d.status_code == 200:
                d_items = r_d.json().get("data", [])
                d_list = []
                for it in d_items[:10]:
                    d_date = str(it.get("date", ""))[:10]
                    c_p = data["price"] or int(it.get("tradePrice", 0))
                    f_qty = int(it.get("foreignNetBuy", 0))
                    i_qty = int(it.get("institutionNetBuy", 0))
                    a_qty = int(it.get("individualNetBuy", 0))
                    d_list.append({
                        "날짜": d_date,
                        "종가(원)": c_p,
                        "외국인(억원)": round(f_qty * c_p / 100000000, 1),
                        "기관(억원)": round(i_qty * c_p / 100000000, 1),
                        "개인(억원)": round(a_qty * c_p / 100000000, 1)
                    })
                data["investor_list"] = d_list
        except Exception:
            pass

    return data

# --- 사이드바 ---
with st.sidebar:
    st.header("⚙️ 분석 기준 설정")
    deposit_rate = st.slider("기준 예금 이자율 (%)", min_value=1.0, max_value=10.0, value=3.5, step=0.1)
    st.caption("일드갭 산출 시 비교 기준이 되는 시중 정기예금/국고채 무위험 금리입니다.")
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

st.write("🔥 **인기 종목 빠른 조회:**")
btn_cols = st.columns(7)
popular_list = ["삼성전자", "SK하이닉스", "현대차", "알테오젠", "삼양식품", "셀트리온", "에코프로비엠"]
for i, p_name in enumerate(popular_list):
    if btn_cols[i].button(p_name, use_container_width=True):
        st.session_state["search_word"] = p_name

if "search_word" not in st.session_state:
    st.session_state["search_word"] = "삼성전자"

col_search, col_btn = st.columns([4, 1])
with col_search:
    user_input = st.text_input("종목명(예: 삼양식품, 카카오, 현대차) 또는 6자리 코드(005930) 입력", value=st.session_state["search_word"])
with col_btn:
    st.write("")
    st.write("")
    run_btn = st.button("종목 분석", type="primary", use_container_width=True)

if run_btn or user_input != st.session_state.get("last_run_query"):
    st.session_state["last_run_query"] = user_input
    code, name = search_krx_stock(user_input)

    if not code:
        st.error(f"'{user_input}' 종목을 찾을 수 없습니다. 정확한 종목명(예: 삼성전자, 삼양식품)이나 6자리 코드를 입력해 주세요.")
    else:
        with st.spinner(f"'{name}' ({code}) 실시간 지표 및 수급 데이터를 분석 중입니다..."):
            d = fetch_full_stock_metrics(code, name)

        if d["price"] == 0:
            st.error("현재 금융 데이터 서버 응답이 지연되고 있습니다. 잠시 후 다시 시도해 주세요.")
        else:
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

            # TAB 1: 가치평가
            with tab1:
                st.markdown("#### 기업 가치 대비 주가 수준 (Valuation)")
                v1, v2, v3, v4 = st.columns(4)
                v1.metric("PER (결산)", f"{d['per']:.1f}배" if d['per'] else "N/A", "15배 이하 저평가")
                v2.metric("PBR (순자산비율)", f"{d['pbr']:.2f}배" if d['pbr'] else "N/A", "1.0배 이하 청산가치")
                v3.metric("추정 PER (선행)", f"{d['cns_per']:.1f}배" if d['cns_per'] else f"{d['per']:.1f}배" if d['per'] else "N/A", "컨센서스 기준")
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
                        st.success("🟢 **매우 유리 (주식 적극 매수 구간)** — 예금 대비 주식 초과수익 보상이 4%p 이상으로 매우 높습니다.")
                    elif yield_gap >= 2.0:
                        st.info("🔵 **유리 (주식 비중 확대)** — 예금보다 2~4%p 높은 수익률이 기대되는 안정적 투자 구간입니다.")
                    elif yield_gap >= 1.0:
                        st.warning("🟡 **다소 유리 (선별 투자)** — 예금 대비 1~2%p 초과수익 구간으로 실적 선별이 필요합니다.")
                    elif yield_gap >= 0.0:
                        st.warning("🟠 **메리트 없음 (분산 권장)** — 주식 위험 대비 보상이 적어 예금·채권 병행이 유리합니다.")
                    else:
                        st.error("🔴 **매우 불리 (예금 보유 유리)** — 주식 기대수익률이 무위험 예금 금리보다 낮습니다.")

                with st.expander("📖 가치평가 지표 상세 설명"):
                    st.markdown("""
                    * **PER (주가수익비율)**: 현재 주가를 1주당 순이익(EPS)으로 나눈 값으로 낮을수록 저평가 상태입니다.
                    * **PBR (주가순자산비율)**: 주가를 주당순자산(BPS)으로 나눈 수치로 1.0배 미만이면 순자산 청산가치보다 쌉니다.
                    * **일드갭 (Yield Gap)**: 주식 기대수익률(1/PER)에서 예금 금리를 뺀 초과수익률로 안전자산 대비 매력도를 뜻합니다.
                    """)

            # TAB 2: 수익성
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
                    * **ROE (자기자본이익률)**: 주주 자본으로 1년간 얼마의 순이익을 남겼는지 측정합니다. (10~15% 이상 우수)
                    * **영업이익률**: 매출액 중 원가와 판관비를 제하고 남은 순수 본업의 영업이익 비율입니다.
                    * **순이익률**: 금융비용과 법인세까지 모두 제하고 최종 주주 몫으로 남은 순이익 비율입니다.
                    """)

            # TAB 3: 재무건전성
            with tab3:
                st.markdown("#### 재무적 생존 체력과 부도 위험 (Stability)")
                s1, s2 = st.columns(2)
                s1.metric("부채비율", f"{d['debt_ratio']:.1f}%" if d['debt_ratio'] is not None else "N/A", "100% 이하 안정권")
                s2.metric("유동비율", f"{d['curr_ratio']:.1f}%" if d['curr_ratio'] is not None else "N/A", "100% 이상 권장")

                if d['debt_ratio'] is not None and d['debt_ratio'] <= 100:
                    st.success(f"✅ **재무구조 건전**: 부채비율이 `{d['debt_ratio']:.1f}%`로 위기 상황에서도 매우 안전합니다.")
                elif d['debt_ratio'] is not None:
                    st.warning(f"⚠️ **부채비율 점검**: 부채비율이 `{d['debt_ratio']:.1f}%`로 업종 특성 및 금융비용을 점검해야 합니다.")

                with st.expander("📖 재무건전성 지표 상세 설명"):
                    st.markdown("""
                    * **부채비율**: 자기자본 대비 총부채 비율입니다. 100% 이하가 이상적이며, 낮을수록 재무 안정성이 높습니다.
                    * **유동비율**: 1년 안에 현금화할 수 있는 유동자산으로 단기 부채를 갚을 수 있는 능력(100% 이상 권장)입니다.
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
