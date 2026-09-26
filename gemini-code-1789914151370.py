import streamlit as st
import pandas as pd
import requests
import yfinance as yf
from bs4 import BeautifulSoup
import re

st.set_page_config(
    page_title="금융 진단 & 거시경제 대시보드",
    page_icon="📈",
    layout="wide"
)

# ==========================================
# 0. 사이드바 대시보드 네비게이션
# ==========================================
with st.sidebar:
    st.title("🧭 메뉴 선택")
    app_mode = st.radio(
        "이동할 대시보드를 선택하세요:",
        ["🏢 종목별 재무·일드갭 진단", "🌍 한·미 주요 경제지표 대시보드"]
    )
    st.divider()

# =========================================================================
# 모드 1: 종목별 재무 · 일드갭 진단기
# =========================================================================
if app_mode == "🏢 종목별 재무·일드갭 진단":
    # 마스터 종목 사전
    MASTER_STOCKS = {
        "005930": "삼성전자", "005935": "삼성전자우", "000660": "SK하이닉스", "042700": "한미반도체",
        "403870": "HPSP", "058470": "리노공업", "000990": "DB하이텍", "039030": "이오테크닉스",
        "373220": "LG에너지솔루션", "006400": "삼성SDI", "051910": "LG화학", "005490": "POSCO홀딩스",
        "003670": "포스코퓨처엠", "247540": "에코프로비엠", "086520": "에코프로", "005380": "현대차",
        "000270": "기아", "012330": "현대모비스", "207940": "삼성바이오로직스", "068270": "셀트리온",
        "196170": "알테오젠", "028300": "HLB", "000250": "삼천당제약", "000100": "유한양행",
        "328130": "루닛", "096530": "씨젠", "035420": "NAVER", "035720": "카카오",
        "259960": "크래프톤", "352820": "하이브", "105560": "KB금융", "055550": "신한지주",
        "034020": "두산에너빌리티", "012450": "한화에어로스페이스", "003230": "삼양식품", "004370": "농심",
        "028260": "삼성물산", "017670": "SK텔레콤", "033780": "KT&G", "066570": "LG전자"
    }
    DROPDOWN_OPTIONS = sorted([f"{name} ({code})" for code, name in MASTER_STOCKS.items()])

    def resolve_stock(query):
        q = query.strip()
        if not q: return None, None
        if q.isdigit() and len(q) == 6:
            return q, MASTER_STOCKS.get(q, f"종목 {q}")
        clean_q = q.lower().replace(" ", "")
        for code, name in MASTER_STOCKS.items():
            if name.lower().replace(" ", "") == clean_q:
                return code, name
        try:
            url = "https://ac.finance.naver.com/ac"
            params = {"q": q, "q_enc": "utf-8", "st": "1", "r_format": "json", "r_enc": "utf-8"}
            headers = {"User-Agent": "Mozilla/5.0"}
            res = requests.get(url, params=params, headers=headers, timeout=3)
            if res.status_code == 200:
                items = res.json().get("items", [[]])[0]
                if items:
                    for it in items:
                        if len(it) >= 2 and it[0].replace(" ", "") == q.replace(" ", ""):
                            return it[1], it[0]
                    if len(items[0]) >= 2:
                        return items[0][1], items[0][0]
        except Exception:
            pass
        return None, None

    @st.cache_data(ttl=180)
    def fetch_stock_all_metrics(code, stock_name):
        data = {
            "code": code, "name": stock_name, "market": "코스피",
            "price": 0, "change_pct": 0.0, "per": None, "cns_per": None, "pbr": None,
            "eps": None, "bps": None, "div_yield": None, "roe": None,
            "op_margin": None, "net_margin": None, "debt_ratio": None, "curr_ratio": None
        }
        headers_m = {
            "User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 16_5 like Mac OS X) AppleWebKit/605.1.15",
            "Referer": f"https://m.stock.naver.com/domestic/stock/{code}/total"
        }
        try:
            rb = requests.get(f"https://m.stock.naver.com/api/stock/{code}/basic", headers=headers_m, timeout=4)
            if rb.status_code == 200:
                jb = rb.json()
                data["name"] = jb.get("stockName") or stock_name
                data["price"] = int(str(jb.get("closePrice", "0")).replace(",", ""))
                data["change_pct"] = float(str(jb.get("fluctuationsRatio", "0")).replace("%", "").strip())
                data["market"] = "코스닥 (KOSDAQ)" if "코스닥" in str(jb.get("stockType", "")) else "코스피 (KOSPI)"
        except Exception: pass

        try:
            ri = requests.get(f"https://m.stock.naver.com/api/stock/{code}/integration", headers=headers_m, timeout=4)
            if ri.status_code == 200:
                for item in ri.json().get("totalInfos", []):
                    k, v = item.get("key", ""), str(item.get("value", "")).replace(",", "").strip()
                    try:
                        if k == "PER" and data["per"] is None: data["per"] = float(v.replace("배", ""))
                        elif k == "PBR" and data["pbr"] is None: data["pbr"] = float(v.replace("배", ""))
                        elif "추정PER" in k and data["cns_per"] is None: data["cns_per"] = float(v.replace("배", ""))
                        elif "배당수익률" in k and data["div_yield"] is None: data["div_yield"] = float(v.replace("%", ""))
                        elif k == "EPS" and data["eps"] is None: data["eps"] = float(v.replace("원", ""))
                        elif k == "BPS" and data["bps"] is None: data["bps"] = float(v.replace("원", ""))
                    except Exception: pass
        except Exception: pass

        if data["price"] == 0 or data["per"] is None or data["pbr"] is None:
            try:
                rd = requests.get(f"https://finance.daum.net/api/quotes/A{code}", headers={"User-Agent": "Mozilla/5.0", "Referer": "https://finance.daum.net/"}, timeout=3)
                if rd.status_code == 200:
                    jd = rd.json()
                    if data["price"] == 0 and jd.get("tradePrice"): data["price"] = int(jd["tradePrice"])
                    if data["per"] is None and jd.get("per"): data["per"] = float(jd["per"])
                    if data["pbr"] is None and jd.get("pbr"): data["pbr"] = float(jd["pbr"])
            except Exception: pass

        try:
            for sfx in [".KS", ".KQ"]:
                inf = yf.Ticker(f"{code}{sfx}").info
                if inf and (inf.get("regularMarketPrice") or inf.get("currentPrice")):
                    if data["price"] == 0: data["price"] = int(inf.get("currentPrice") or inf.get("regularMarketPrice") or 0)
                    if data["per"] is None and inf.get("trailingPE"): data["per"] = round(float(inf["trailingPE"]), 1)
                    if data["pbr"] is None and inf.get("priceToBook"): data["pbr"] = round(float(inf["priceToBook"]), 2)
                    if data["roe"] is None and inf.get("returnOnEquity"): data["roe"] = round(float(inf["returnOnEquity"]) * 100, 1)
                    if data["op_margin"] is None and inf.get("operatingMargins"): data["op_margin"] = round(float(inf["operatingMargins"]) * 100, 1)
                    if data["debt_ratio"] is None and inf.get("debtToEquity"): data["debt_ratio"] = round(float(inf["debtToEquity"]), 1)
                    break
        except Exception: pass

        if data["roe"] is None and data["pbr"] and data["per"] and data["per"] > 0:
            data["roe"] = round((data["pbr"] / data["per"]) * 100, 1)

        return data

    with st.sidebar:
        st.header("⚙️ 분석 기준 설정")
        deposit_rate = st.slider("기준 예금 이자율 (%)", min_value=1.0, max_value=10.0, value=3.5, step=0.1)
        st.caption("일드갭 산출 시 비교 기준이 되는 시중 정기예금/국고채 무위험 금리입니다.")

    st.title("📈 국내주식 종목별 주요지표 분석")
    st.caption("가치평가 · 수익성 · 재무건전성 종합 진단")

    btn_cols = st.columns(7)
    for i, p_name in enumerate(["삼성전자", "SK하이닉스", "현대차", "삼양식품", "알테오젠", "루닛", "셀트리온"]):
        if btn_cols[i].button(p_name, use_container_width=True):
            st.session_state["target_input"] = p_name

    if "target_input" not in st.session_state:
        st.session_state["target_input"] = "삼성전자"

    c_in, c_btn = st.columns([4, 1])
    with c_in:
        user_query = st.text_input("종목명 또는 6자리 코드 입력", value=st.session_state["target_input"])
    with c_btn:
        st.write("")
        st.write("")
        run_btn = st.button("종목 분석", type="primary", use_container_width=True)

    with st.expander("📋 대표 상장사 목록에서 선택"):
        sel_item = st.selectbox("종목 선택", options=["선택하세요..."] + DROPDOWN_OPTIONS, index=0)
        if sel_item != "선택하세요...":
            user_query = sel_item.split("(")[0].strip()

    if run_btn or user_query != st.session_state.get("last_search"):
        st.session_state["last_search"] = user_query
        target_code, target_name = resolve_stock(user_query)

        if not target_code:
            st.error(f"'{user_query}' 종목을 찾을 수 없습니다. 정확한 종목명이나 6자리 코드를 입력해 주세요.")
        else:
            with st.spinner(f"'{target_name}' ({target_code}) 분석 중..."):
                d = fetch_stock_all_metrics(target_code, target_name)

            if not d or d["price"] == 0:
                st.error("종목 시세를 불러올 수 없습니다. 코드를 확인해 주세요.")
            else:
                st.divider()
                h1, h2, h3 = st.columns([2, 1, 1])
                h1.subheader(f"🏢 {d['name']} ({d['code']})")
                h2.metric("현재 주가", f"{d['price']:,.0f}원", f"{d['change_pct']:+.2f}%" if d['change_pct'] != 0 else "")
                h3.write(f"**소속 시장:** `{d['market']}`")

                t1, t2, t3 = st.tabs(["💰 1. 가치평가 지표 (일드갭)", "📈 2. 수익성 지표", "🛡️ 3. 재무건전성 지표"])
                with t1:
                    v1, v2, v3, v4 = st.columns(4)
                    v1.metric("PER", f"{d['per']:.1f}배" if d['per'] else "적자 기업", "15배 이하 저평가")
                    v2.metric("PBR", f"{d['pbr']:.2f}배" if d['pbr'] else "N/A", "1.0배 이하 청산가치")
                    v3.metric("선행 PER", f"{d['cns_per']:.1f}배" if d['cns_per'] else (f"{d['per']:.1f}배" if d['per'] else "N/A"))
                    v4.metric("배당수익률", f"{d['div_yield']:.2f}%" if d['div_yield'] is not None else "0.00%")

                    base_per = d['cns_per'] or d['per']
                    if base_per and base_per > 0:
                        exp_ret = (1 / base_per) * 100
                        yield_gap = exp_ret - deposit_rate
                        st.markdown("##### 📌 벤저민 그레이엄 일드갭 진단")
                        yc1, yc2, yc3 = st.columns(3)
                        yc1.metric("주식 기대수익률 (1/PER)", f"{exp_ret:.2f}%")
                        yc2.metric("기준 예금 이자율", f"{deposit_rate:.2f}%")
                        yc3.metric("일드갭 (초과수익률)", f"{yield_gap:+.2f}%p")
                        if yield_gap >= 4.0: st.success("🟢 **매우 유리 (주식 적극 매수 구간)**: 예금 대비 보상이 4%p 이상으로 기대수익이 매우 높습니다.")
                        elif yield_gap >= 2.0: st.info("🔵 **유리 (비중 확대)**: 예금보다 2~4%p 높은 수익률이 기대되는 안정적 구간입니다.")
                        elif yield_gap >= 1.0: st.warning("🟡 **다소 유리 (선별 투자)**: 예금 대비 1~2%p 초과수익 구간입니다.")
                        elif yield_gap >= 0.0: st.warning("🟠 **메리트 없음**: 예금·채권 병행이 유리합니다.")
                        else: st.error("🔴 **매우 불리**: 주식 기대수익률이 무위험 예금 금리보다 낮습니다.")

                with t2:
                    p1, p2 = st.columns(2)
                    p1.metric("ROE (자기자본이익률)", f"{d['roe']:.1f}%" if d['roe'] is not None else "N/A", "10% 이상 우수")
                    p2.metric("영업이익률", f"{d['op_margin']:.1f}%" if d['op_margin'] is not None else "N/A", "본업 경쟁력")

                with t3:
                    s1 = st.columns(1)[0]
                    s1.metric("부채비율", f"{d['debt_ratio']:.1f}%" if d['debt_ratio'] is not None else "N/A", "100% 이하 안정권")

# =========================================================================
# 모드 2: 한·미 주요 경제지표 대시보드
# =========================================================================
else:
    st.title("🌍 한·미 주요 경제지표 대시보드")
    st.caption("글로벌 거시경제 핵심 지표(환율·금리·원자재·증시·리스크) 실시간 동향 및 시황 해설")

    MACRO_DICT = {
        "환율 & 통화": {
            "원/달러 환율": {"sym": "KRW=X", "unit": "원", "desc": "원화 가치 척도. 상승(원화 약세) 시 외인 자본 유출 압력 가중 및 수입 물가 상승."},
            "달러 인덱스": {"sym": "DX-Y.NYB", "unit": "pt", "desc": "주요 6개국 통화 대비 달러 가치. 상승 시 신흥국 시장에서 달러 회수 압력 심화."}
        },
        "금리 & 채권": {
            "미국 국채 10년물 금리": {"sym": "^TNX", "unit": "%", "desc": "글로벌 장기 기준금리. 급등 시 미래 가치를 땡겨오는 성장주/기술주 밸류에이션 부담."},
            "미국 국채 5년물 금리": {"sym": "^FVX", "unit": "%", "desc": "중기 경기 전망 및 연준 통화정책 기대를 민감하게 반영하는 핵심 채권 금리."}
        },
        "원자재 & 인플레이션": {
            "WTI 국제유가": {"sym": "CL=F", "unit": "$/bbl", "desc": "글로벌 생산·물류의 혈액. 급등 시 원자재 수입 비중이 큰 한국 무역수지 악화."},
            "국제 금 시세": {"sym": "GC=F", "unit": "$/oz", "desc": "대표적인 실물 안전자산. 지정학적 위기나 화폐 가치 하락(인플레이션) 시 급등."},
            "구리 선물 (닥터 코퍼)": {"sym": "HG=F", "unit": "$/lb", "desc": "실물 경제 선행 지표. 건설·전기차 등 산업 전반에 쓰여 경기 호황 시 강세."}
        },
        "증시 지수 & 공포 지수": {
            "S&P 500": {"sym": "^GSPC", "unit": "pt", "desc": "미국 대형주 500개 대표 지수. 글로벌 위험자산의 전반적인 방향타."},
            "나스닥 종합": {"sym": "^IXIC", "unit": "pt", "desc": "글로벌 빅테크 및 첨단 기술주 집합소. 한국 IT/반도체 주가와 높은 동조화."},
            "코스피 지수": {"sym": "^KS11", "unit": "pt", "desc": "대한민국 대표 유가증권시장. 수출 경기 및 글로벌 유동성에 매우 민감."},
            "VIX 변동성 지수": {"sym": "^VIX", "unit": "pt", "desc": "월가의 '공포 지수'. 20 미만은 안정 국면, 30 이상은 시장 패닉(투매)을 의미."}
        }
    }

    @st.cache_data(ttl=300)
    def fetch_macro_series():
        results = {}
        for category, items in MACRO_DICT.items():
            results[category] = {}
            for name, meta in items.items():
                try:
                    ticker = yf.Ticker(meta["sym"])
                    hist = ticker.history(period="1mo")
                    if not hist.empty and len(hist) >= 2:
                        curr = float(hist["Close"].iloc[-1])
                        prev = float(hist["Close"].iloc[-2])
                        chg_pct = ((curr - prev) / prev) * 100
                        results[category][name] = {
                            "current": curr,
                            "change": chg_pct,
                            "unit": meta["unit"],
                            "desc": meta["desc"],
                            "history": hist["Close"]
                        }
                    elif not hist.empty:
                        curr = float(hist["Close"].iloc[-1])
                        results[category][name] = {
                            "current": curr,
                            "change": 0.0,
                            "unit": meta["unit"],
                            "desc": meta["desc"],
                            "history": hist["Close"]
                        }
                except Exception:
                    pass
        return results

    with st.spinner("글로벌 거시경제 데이터를 집계 중입니다..."):
        macro_data = fetch_macro_series()

    st.markdown("### 📌 부문별 실시간 핵심 지표 현황")

    for cat_name, cat_items in macro_data.items():
        st.subheader(f"📊 {cat_name}")
        cols = st.columns(len(cat_items) if cat_items else 1)

        idx = 0
        for name, d in cat_items.items():
            with cols[idx]:
                fmt_val = f"{d['current']:,.2f} {d['unit']}" if d['unit'] != "원" else f"{d['current']:,.1f} {d['unit']}"
                st.metric(
                    label=name,
                    value=fmt_val,
                    delta=f"{d['change']:+.2f}%"
                )
                with st.expander("📖 지표 의미 & 투자 영향"):
                    st.write(d["desc"])
                    st.line_chart(d["history"], height=120)
            idx += 1
        st.divider()

    st.markdown("### 💡 거시경제 지표 종합 판독 가이드")
    st.markdown("""
    1. **환율과 금리의 삼각관계**:
       * **미국 국채 금리 상승 $\rightarrow$ 달러 인덱스 상승 $\rightarrow$ 원/달러 환율 상승(원화 약세)**으로 연결되기 쉽습니다.
       * 원/달러 환율이 가파르게 상승하면 외국인 투자자는 환차손을 피하기 위해 코스피 대형주(삼성전자, 현대차 등)를 순매도하는 경향이 강해집니다.
    2. **구리와 유가(인플레이션과 경기)**:
       * **구리 가격 상승 + 유가 안정**: 제조업 경기 확장 국면으로 수출 비중이 큰 한국 증시에 가장 우호적인 환경입니다.
       * **구리 가격 하락 + 유가 급등**: 전형적인 스태그플레이션(경기 둔화 속 물가 상승) 위험 신호로, 기업 이익 마진이 압박을 받습니다.
    3. **VIX(공포 지수)를 활용한 역발상 투자**:
       * VIX가 **20 이하**일 때는 시장이 과도한 낙관론에 취약할 수 있습니다.
       * VIX가 **30~40 이상**으로 치솟는 투매 구간은 공포가 극에 달한 시점으로, 우량주 분할 매수의 안전마진이 커지는 시기입니다.
    """)
