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

# 대표 주요 종목 코드 사전 (즉시 매핑)
POPULAR_STOCKS = {
    "삼성전자": "005930", "sk하이닉스": "000660", "현대차": "005380",
    "기아": "000270", "lg에너지솔루션": "373220", "삼성바이오로직스": "207940",
    "셀트리온": "068270", "kb금융": "105560", "신한지주": "055550",
    "포스코홀딩스": "005490", "posco홀딩스": "005490", "naver": "035420",
    "네이버": "035420", "카카오": "035720", "에코프로비엠": "247540",
    "에코프로": "086520", "알테오젠": "196170", "hlb": "028300",
    "삼천당제약": "000250", "한미반도체": "042700", "두산에너빌리티": "034020",
    "한화에어로스페이스": "012450", "크래프톤": "259960", "카카오뱅크": "323410",
    "lg전자": "066570", "현대모비스": "012330", "삼성sdi": "006400",
    "lg화학": "051910", "kt&g": "033780", "하나금융지주": "086790"
}

# 종목명 -> 6자리 코드 변환 함수
def resolve_code(query):
    q = query.strip()
    if q.isdigit() and len(q) == 6:
        return q
    q_clean = q.lower().replace(" ", "")
    if q_clean in POPULAR_STOCKS:
        return POPULAR_STOCKS[q_clean]
    try:
        url = f"https://finance.naver.com/search/searchList.naver?query={requests.utils.quote(q.encode('cp949'))}"
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
        r = requests.get(url, headers=headers, timeout=5)
        m = re.search(r"/item/main\.naver\?code=(\d{6})", r.text)
        if m:
            return m.group(1)
    except Exception:
        pass
    return None

# 네이버 금융 데이터 수집 함수 (FnGuide 공시 기준)
@st.cache_data(ttl=300)
def fetch_stock_data(code):
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
        "Referer": "https://finance.naver.com/"
    }
    
    # 1. 메인 재무 데이터
    url_main = f"https://finance.naver.com/item/main.naver?code={code}"
    res = requests.get(url_main, headers=headers, timeout=5)
    res.encoding = "cp949"
    soup = BeautifulSoup(res.text, "html.parser")

    name = code
    wrap = soup.find("div", class_="wrap_company")
    if wrap and wrap.find("h2"):
        name = wrap.find("h2").text.strip()

    price = 0
    no_today = soup.find("p", class_="no_today")
    if no_today and no_today.find("span", class_="blind"):
        try:
            price = int(no_today.find("span", class_="blind").text.replace(",", ""))
        except Exception:
            pass

    market_type = "코스닥" if (soup.find("div", class_="description") and "코스닥" in soup.find("div", class_="description").text) else "코스피"

    change_pct = 0.0
    no_exday = soup.find("p", class_="no_exday")
    if no_exday:
        blinds = no_exday.find_all("span", class_="blind")
        if len(blinds) >= 2:
            try:
                rate = float(blinds[1].text.replace("%", "").strip())
                if "no_down" in str(no_exday) or "nv" in str(no_exday):
                    rate = -rate
                change_pct = rate
            except Exception:
                pass

    def get_val(id_name):
        tag = soup.find(id=id_name)
        if tag:
            try:
                return float(tag.text.replace(",", "").strip())
            except Exception:
                return None
        return None

    per = get_val("_per")
    eps = get_val("_eps")
    pbr = get_val("_pbr")
    dvr = get_val("_dvr")
    cns_per = get_val("_cns_per")

    # 2. 기업실적분석 테이블 (ROE, 영업이익률, 부채비율, 당좌비율)
    fin_table = soup.find("table", class_="tb_type1_ifrs") or soup.find("table", class_="tb_type1")
    roe, op_margin, net_margin, debt_ratio, curr_ratio = None, None, None, None, None

    if fin_table:
        for tr in fin_table.find_all("tr"):
            th = tr.find("th")
            if not th:
                continue
            title = th.text.strip()
            tds = tr.find_all("td")
            vals = []
            for td in tds:
                t = td.text.replace(",", "").strip()
                try:
                    vals.append(float(t))
                except Exception:
                    pass
            last_v = vals[-1] if vals else None
            
            if "ROE" in title and roe is None:
                roe = last_v
            elif "영업이익률" in title and op_margin is None:
                op_margin = last_v
            elif "순이익률" in title and net_margin is None:
                net_margin = last_v
            elif "부채비율" in title and debt_ratio is None:
                debt_ratio = last_v
            elif ("당좌비율" in title or "유동비율" in title) and curr_ratio is None:
                curr_ratio = last_v

    if roe is None and per and pbr and per > 0:
        roe = round((pbr / per) * 100, 1)

    # 3. 최근 10영업일 수급 (frgn.naver)
    investor_list = []
    try:
        url_frgn = f"https://finance.naver.com/item/frgn.naver?code={code}"
        res_f = requests.get(url_frgn, headers=headers, timeout=5)
        res_f.encoding = "cp949"
        soup_f = BeautifulSoup(res_f.text, "html.parser")
        table_f = soup_f.find("table", class_="type2")
        if table_f:
            for tr in table_f.find_all("tr"):
                tds = tr.find_all("td")
                if len(tds) >= 7:
                    d_str = tds[0].text.strip()
                    if re.match(r"\d{4}\.\d{2}\.\d{2}", d_str):
                        c_p = int(tds[1].text.strip().replace(",", ""))
                        inst_q = int(tds[5].text.strip().replace(",", ""))
                        fore_q = int(tds[6].text.strip().replace(",", ""))
                        investor_list.append({
                            "날짜": d_str,
                            "종가(원)": c_p,
                            "외국인(억원)": round(fore_q * c_p / 100000000, 1),
                            "기관(억원)": round(inst_q * c_p / 100000000, 1)
                        })
                        if len(investor_list) >= 10:
                            break
    except Exception:
        pass

    return {
        "name": name, "code": code, "market": market_type,
        "price": price, "change_pct": change_pct,
        "per": per, "cns_per": cns_per, "eps": eps, "pbr": pbr, "dvr": dvr,
        "roe": roe, "op_margin": op_margin, "net_margin": net_margin,
        "debt_ratio": debt_ratio, "curr_ratio": curr_ratio,
        "investor_list": investor_list
    }

# --- 사이드바 ---
with st.sidebar:
    st.header("⚙️ 분석 기준 설정")
    deposit_rate = st.slider("기준 예금 이자율 (%)", min_value=1.0, max_value=10.0, value=3.5, step=0.1)
    st.info("💡 종목명(예: 현대차) 또는 6자리 코드(005380)를 입력하면 모든 지표와 수급이 자동 계산됩니다.")

# --- 메인 헤더 ---
st.title("📈 국내주식 종목별 주요지표 분석")
st.caption("가치평가 · 수익성 · 재무건전성 & 성장성 종합 진단 및 최근 10영업일 기관/외국인 수급 추이")

col_search, col_btn = st.columns([4, 1])
with col_search:
    search_input = st.text_input("종목명 또는 6자리 코드 입력", value="삼성전자")
with col_btn:
    st.write("")
    st.write("")
    run_btn = st.button("종목 분석", type="primary", use_container_width=True)

if run_btn or "saved_code" in st.session_state:
    if run_btn:
        c = resolve_code(search_input)
        if not c:
            st.error(f"'{search_input}' 종목을 찾을 수 없습니다. 정확한 종목명이나 6자리 코드를 입력해 주세요.")
            st.stop()
        st.session_state["saved_code"] = c
    else:
        c = st.session_state["saved_code"]

    with st.spinner("실시간 공시 및 재무 데이터 분석 중..."):
        d = fetch_stock_data(c)

    if not d or d["price"] == 0:
        st.error("데이터를 불러오지 못했습니다. 종목코드를 다시 확인해 주세요.")
        st.stop()

    st.divider()
    h1, h2, h3 = st.columns([2, 1, 1])
    h1.subheader(f"🏢 {d['name']} ({d['code']})")
    h2.metric("현재가", f"{d['price']:,.0f}원", f"{d['change_pct']:+.2f}%")
    h3.write(f"**소속 시장:** `{d['market']}`")

    t1, t2, t3, t4 = st.tabs([
        "💰 1. 가치평가 지표",
        "📈 2. 수익성 지표",
        "🛡️ 3. 재무건전성 지표",
        "👥 4. 최근 10영업일 수급 동향"
    ])

    # 1. 가치평가
    with t1:
        st.markdown("#### 기업 가치 대비 주가 수준 (Valuation)")
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("PER (결산)", f"{d['per']:.1f}배" if d['per'] else "N/A", "15배 이하 저평가")
        c2.metric("PBR", f"{d['pbr']:.2f}배" if d['pbr'] else "N/A", "1.0배 이하 청산가치")
        c3.metric("추정 PER (컨센서스)", f"{d['cns_per']:.1f}배" if d['cns_per'] else "N/A", "선행 실적 기준")
        c4.metric("배당수익률", f"{d['dvr']:.2f}%" if d['dvr'] else "0.00%", "3% 이상 안전마진")

        st.markdown("##### 📌 벤저민 그레이엄 일드갭(초과수익률) 진단")
        base_per = d['cns_per'] or d['per']
        if base_per and base_per > 0:
            exp_ret = (1 / base_per) * 100
            gap = exp_ret - deposit_rate

            yc1, yc2, yc3 = st.columns(3)
            yc1.metric("주식 기대수익률 (1/PER)", f"{exp_ret:.2f}%", f"적용 PER {base_per:.1f}배")
            yc2.metric("기준 예금 이자율", f"{deposit_rate:.2f}%")
            yc3.metric("일드갭 (초과수익률)", f"{gap:+.2f}%p")

            if gap >= 4.0:
                st.success("🟢 **매우 유리 (주식 적극 매수 구간)** — 예금 금리 대비 주식 초과수익 보상이 4%p 이상으로 매우 높습니다.")
            elif gap >= 2.0:
                st.info("🔵 **유리 (주식 비중 확대)** — 예금보다 2~4%p 높은 수익률이 기대되는 안정적 구간입니다.")
            elif gap >= 1.0:
                st.warning("🟡 **다소 유리 (선별적 접근)** — 예금 대비 1~2%p 초과수익 구간으로 개별 실적 검토가 필요합니다.")
            elif gap >= 0.0:
                st.warning("🟠 **메리트 없음 (분산 권장)** — 주식 위험 대비 보상이 적어 예금·채권 병행이 유리합니다.")
            else:
                st.error("🔴 **매우 불리 (예금 보유 유리)** — 주식 기대수익률이 무위험 예금 금리보다 낮습니다.")

        with st.expander("📖 가치평가 지표 상세 설명"):
            st.markdown("""
            * **PER (주가수익비율)**: 현재 주가를 주당순이익(EPS)으로 나눈 값으로, 낮을수록 기업이 벌어들이는 이익 대비 주가가 저평가되어 있음을 뜻합니다.
            * **PBR (주가순자산비율)**: 현재 주가를 1주당 순자산(BPS)으로 나눈 값으로, 1.0배 미만이면 회사 자산을 전부 처분해도 주가보다 많은 자산 저평가 상태입니다.
            * **일드갭 (Yield Gap)**: 주식 기대수익률(1/PER)에서 국채나 예금 금리를 뺀 초과수익률로, 채권/예금 대비 주식 투자의 매력도를 직접 비교합니다.
            """)

    # 2. 수익성
    with t2:
        st.markdown("#### 돈을 버는 효율성과 마진율 (Profitability)")
        p1, p2, p3 = st.columns(3)
        p1.metric("ROE (자기자본이익률)", f"{d['roe']:.1f}%" if d['roe'] else "N/A", "10% 이상 우량")
        p2.metric("영업이익률", f"{d['op_margin']:.1f}%" if d['op_margin'] else "N/A", "본업 경쟁력")
        p3.metric("당기순이익률", f"{d['net_margin']:.1f}%" if d['net_margin'] else "N/A", "최종 마진율")

        if d['roe'] and d['roe'] >= 10:
            st.success(f"✅ **수익성 우수**: ROE가 `{d['roe']:.1f}%`로 자기자본 대비 매우 우수한 이익 창출력을 입증하고 있습니다.")
        elif d['roe']:
            st.info(f"ℹ️ **수익성 보통**: ROE가 `{d['roe']:.1f}%` 수준입니다.")

        with st.expander("📖 수익성 지표 상세 설명"):
            st.markdown("""
            * **ROE (자기자본이익률)**: 주주들이 맡긴 자본으로 1년간 얼마의 순이익을 벌어들였는지 측정하는 지표입니다. 워런 버핏은 지속적으로 15% 이상 유지되는 기업을 강력한 해자를 지닌 우량 기업으로 평가했습니다.
            * **영업이익률**: 매출액 중 원가와 판관비를 제하고 남은 순수 영업이익 비율로, 기업의 가격 결정력과 원가 경쟁력을 보여줍니다.
            """)

    # 3. 재무건전성
    with t3:
        st.markdown("#### 재무적 생존 체력과 부도 위험 (Stability)")
        s1, s2 = st.columns(2)
        s1.metric("부채비율", f"{d['debt_ratio']:.1f}%" if d['debt_ratio'] else "N/A", "100% 이하 안정권")
        s2.metric("당좌/유동비율", f"{d['curr_ratio']:.1f}%" if d['curr_ratio'] else "N/A", "100% 이상 안정권")

        if d['debt_ratio'] and d['debt_ratio'] <= 100:
            st.success(f"✅ **재무구조 우량**: 부채비율이 `{d['debt_ratio']:.1f}%`로 위기 상황이나 고금리 국면에서도 안전합니다.")
        elif d['debt_ratio'] and d['debt_ratio'] > 200:
            st.warning(f"⚠️ **부채비율 주의**: 부채비율이 `{d['debt_ratio']:.1f}%`로 이자비용 부담을 점검할 필요가 있습니다.")

        with st.expander("📖 재무건전성 지표 상세 설명"):
            st.markdown("""
            * **부채비율**: 자기자본 대비 총부채의 비율입니다. 100% 이하가 이상적이며, 200% 이상이면 금리 인상기에 이자 부담이 급증할 수 있습니다.
            * **당좌/유동비율**: 단기 부채를 즉각 갚을 수 있는 현금성 자산의 비율로, 100% 이상이어야 단기 자금 경색 위험을 피할 수 있습니다.
            """)

    # 4. 수급
    with t4:
        st.markdown("#### 최근 10영업일 외국인 / 기관 순매수 동향 (단위: 억원)")
        if d['investor_list']:
            df_inv = pd.DataFrame(d['investor_list']).set_index("날짜")
            sum_f = df_inv["외국인(억원)"].sum()
            sum_i = df_inv["기관(억원)"].sum()

            sq1, sq2 = st.columns(2)
            sq1.metric("10일간 외국인 누적 순매수", f"{sum_f:+,.1f} 억원")
            sq2.metric("10일간 기관 누적 순매수", f"{sum_i:+,.1f} 억원")

            if sum_f > 0 and sum_i > 0:
                st.success("🔥 **외인·기관 쌍끌이 순매수**: 메이저 수급 주체들이 동반 매수하며 주가 하방 지지력이 매우 강합니다.")
            elif sum_f < 0 and sum_i < 0:
                st.error("🌧️ **외인·기관 동반 순매도**: 수급 유출이 지속되고 있으므로 보수적인 접근이 권장됩니다.")
            elif sum_f > 0:
                st.info("💡 **외국인 주도 순매수 국면**: 외국인 중심의 자금 유입이 지속되고 있습니다.")
            elif sum_i > 0:
                st.info("💡 **기관 주도 순매수 국면**: 국내 기관(투신/연기금) 중심의 매수세가 유입 중입니다.")

            st.bar_chart(df_inv[["외국인(억원)", "기관(억원)"]])
            st.dataframe(df_inv, use_container_width=True)
        else:
            st.info("수급 데이터를 집계 중입니다. 잠시 후 다시 조회해 주세요.")
