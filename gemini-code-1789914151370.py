import streamlit as st
import pandas as pd
import requests
import yfinance as yf
from datetime import datetime

st.set_page_config(
    page_title="국내주식 종목별 주요지표 분석",
    page_icon="📊",
    layout="wide"
)

# 1. 국내 주요 대표 종목 코드 사전 (즉시 변환)
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

# 2. 데이터 수집 함수 (네이버 모바일 API 1차 시도 -> 실패 시 yfinance 2차 백업)
@st.cache_data(ttl=300)
def fetch_stock_all(code):
    data = {
        "name": code, "code": code, "price": 0, "change_pct": 0.0,
        "per": None, "cns_per": None, "pbr": None, "eps": None, "div_yield": None,
        "roe": None, "op_margin": None, "net_margin": None,
        "debt_ratio": None, "curr_ratio": None,
        "investor_list": [], "source": "Naver Mobile API"
    }

    # --- 엔진 A: 네이버 모바일 전용 JSON API ---
    headers = {
        "User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 16_5 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.5 Mobile/15E148 Safari/604.1",
        "Referer": f"https://m.stock.naver.com/domestic/stock/{code}/total",
        "Origin": "https://m.stock.naver.com"
    }

    try:
        # 기본 시세
        basic_url = f"https://m.stock.naver.com/api/stock/{code}/basic"
        r_basic = requests.get(basic_url, headers=headers, timeout=4)
        if r_basic.status_code == 200:
            jb = r_basic.json()
            data["name"] = jb.get("stockName", code)
            data["price"] = int(str(jb.get("closePrice", "0")).replace(",", ""))
            data["change_pct"] = float(str(jb.get("fluctuationsRatio", "0")).replace("%", "").strip())

        # 통합 재무지표 (PER, PBR, ROE 등)
        int_url = f"https://m.stock.naver.com/api/stock/{code}/integration"
        r_int = requests.get(int_url, headers=headers, timeout=4)
        if r_int.status_code == 200:
            ji = r_int.json()
            # totalInfos 항목 파싱
            for item in ji.get("totalInfos", []):
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

        # 최근 10영업일 수급 (기관/외국인/개인)
        trend_url = f"https://m.stock.naver.com/api/stock/{code}/trend?pageSize=10&page=1"
        r_trend = requests.get(trend_url, headers=headers, timeout=4)
        if r_trend.status_code == 200:
            jt = r_trend.json()
            t_list = []
            for row in jt.get("message", []):
                dt_raw = row.get("bizdate", "")
                c_price = int(str(row.get("closePrice", 0)).replace(",", ""))
                frg_q = int(str(row.get("foreignerPureBuyQuant", 0)).replace(",", ""))
                inst_q = int(str(row.get("organPureBuyQuant", 0)).replace(",", ""))
                ant_q = int(str(row.get("individualPureBuyQuant", 0)).replace(",", ""))

                dt_fmt = f"{dt_raw[:4]}-{dt_raw[4:6]}-{dt_raw[6:]}" if len(dt_raw) == 8 else dt_raw
                # 억원 단위 환산
                t_list.append({
                    "날짜": dt_fmt,
                    "종가(원)": c_price,
                    "외국인(억원)": round(frg_q * c_price / 100000000, 1),
                    "기관(억원)": round(inst_q * c_price / 100000000, 1),
                    "개인(억원)": round(ant_q * c_price / 100000000, 1)
                })
            data["investor_list"] = t_list

    except Exception:
        pass

    # --- 엔진 B: 백업 (해외 서버 차단 시 Yahoo Finance로 안전 전환) ---
    if data["price"] == 0:
        data["source"] = "글로벌 금융 백업 엔진 (Yahoo Finance)"
        try:
            for suffix in [".KS", ".KQ"]:
                stk = yf.Ticker(f"{code}{suffix}")
                info = stk.info
                price = info.get("currentPrice") or info.get("regularMarketPrice") or info.get("previousClose")
                if price:
                    data["name"] = info.get("shortName") or info.get("longName") or code
                    data["price"] = int(price)
                    data["per"] = info.get("trailingPE") or info.get("forwardPE")
                    data["pbr"] = info.get("priceToBook")
                    data["eps"] = info.get("trailingEps")
                    data["div_yield"] = (info.get("dividendYield") * 100) if info.get("dividendYield") else 0.0
                    data["roe"] = (info.get("returnOnEquity") * 100) if info.get("returnOnEquity") else None
                    data["op_margin"] = (info.get("operatingMargins") * 100) if info.get("operatingMargins") else None
                    data["debt_ratio"] = info.get("debtToEquity")
                    break
        except Exception:
            pass

    # ROE가 비어있을 경우 자본 효율 공식(PBR/PER)으로 자동 계산
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

    with st.spinner("실시간 공시 및 금융 데이터 분석 중..."):
        d = fetch_stock_all(target_code)

    if d["price"] == 0:
        st.error("현재 일시적인 네트워크 차단으로 시세를 불러오지 못했습니다. 잠시 후 다시 시도해 주세요.")
        st.stop()

    # 상단 요약 헤더
    st.divider()
    h1, h2, h3 = st.columns([2, 1, 1])
    h1.subheader(f"🏢 {d['name']} ({d['code']})")
    h2.metric("현재 주가", f"{d['price']:,.0f}원", f"{d['change_pct']:+.2f}%" if d['change_pct'] != 0 else "")
    h3.caption(f"데이터 출처: `{d['source']}`")

    # 4대 분석 탭
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
        v1.metric("PER (주가수익비율)", f"{d['per']:.1f}배" if d['per'] else "N/A", "15배 이하 저평가")
        v2.metric("PBR (주가순자산비율)", f"{d['pbr']:.2f}배" if d['pbr'] else "N/A", "1.0배 이하 청산가치")
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
                st.warning("🟡 **다소 유리 (선별 투자)** — 예금 대비 1~2%p 초과수익 구간으로 개별 종목의 펀더멘털 선별이 필요합니다.")
            elif yield_gap >= 0.0:
                st.warning("🟠 **메리트 없음 (분산 권장)** — 주식 위험 대비 보상이 적어 예금·채권 병행이 유리합니다.")
            else:
                st.error("🔴 **매우 불리 (예금 보유 유리)** — 주식 기대수익률이 무위험 예금 금리보다 낮아 확정금리 자산이 유리합니다.")
        else:
            st.info("적자 기업이거나 PER 데이터가 없어 일드갭 계산을 생략합니다.")

        with st.expander("📖 가치평가 지표 상세 설명"):
            st.markdown("""
            * **PER (주가수익비율)**: 현재 주가를 1주당 순이익(EPS)으로 나눈 값입니다. 기업이 벌어들이는 이익에 비해 주가가 몇 배로 거래되는지 나타내며, 10~15배 이하일 때 저평가로 봅니다.
            * **PBR (주가순자산비율)**: 주가를 주당순자산(BPS)으로 나눈 수치입니다. 1.0배 미만이면 회사를 지금 당장 청산하여 순자산을 주주에게 나눠주더라도 현재 주가보다 많다는 뜻으로 강한 하방 지지력을 가집니다.
            * **일드갭 (Yield Gap)**: 주식 기대수익률(1/PER)에서 국채나 은행 예금 금리를 뺀 초과수익률로, 위험을 감수하는 주식 투자가 안전한 예금 대비 얼마나 매력적인지 평가합니다.
            """)

    # 2. 수익성
    with tab2:
        st.markdown("#### 돈을 버는 효율성과 마진율 (Profitability)")
        p1, p2 = st.columns(2)
        p1.metric("ROE (자기자본이익률)", f"{d['roe']:.1f}%" if d['roe'] else "N/A", "10% 이상 우량")
        p2.metric("영업이익률", f"{d['op_margin']:.1f}%" if d['op_margin'] else "N/A", "본업 경쟁력")

        if d['roe'] and d['roe'] >= 10:
            st.success(f"✅ **수익성 우수**: ROE가 `{d['roe']:.1f}%`로 자기자본 대비 매우 훌륭한 복리 이익 창출 능력을 보이고 있습니다.")
        elif d['roe']:
            st.info(f"ℹ️ **수익성 보통**: ROE가 `{d['roe']:.1f}%` 수준입니다.")

        with st.expander("📖 수익성 지표 상세 설명"):
            st.markdown("""
            * **ROE (자기자본이익률)**: 주주들이 투자한 순자본으로 1년간 얼마의 순이익을 창출했는지 측정합니다. 워런 버핏은 연 15% 이상의 높은 ROE를 꾸준히 유지하는 기업을 최고의 경제적 해자 기업으로 꼽았습니다.
            * **영업이익률**: 매출액 중 원가와 판관비를 제하고 남은 순수 영업이익 비율로, 브랜드 가격 결정력과 생산 원가 통제력을 증명합니다.
            """)

    # 3. 재무건전성
    with tab3:
        st.markdown("#### 재무적 생존 체력과 부도 위험 (Stability)")
        s1, s2 = st.columns(2)
        s1.metric("부채비율", f"{d['debt_ratio']:.1f}%" if d['debt_ratio'] else "N/A", "100% 이하 안정권")
        s2.metric("유동/당좌비율", f"{d['curr_ratio']:.1f}%" if d['curr_ratio'] else "N/A", "100% 이상 권장")

        if d['debt_ratio'] and d['debt_ratio'] <= 100:
            st.success(f"✅ **재무 건전**: 부채비율이 `{d['debt_ratio']:.1f}%`로 금리 인상기나 경기 침체기에도 매우 안전합니다.")
        elif d['debt_ratio'] and d['debt_ratio'] > 200:
            st.warning(f"⚠️ **부채비율 과다**: 부채비율이 `{d['debt_ratio']:.1f}%`로 금융비용 부담이 클 수 있으므로 점검이 필요합니다.")

        with st.expander("📖 재무건전성 지표 상세 설명"):
            st.markdown("""
            * **부채비율**: 자기자본 대비 총부채의 비율입니다. 100% 이하가 가장 이상적이며, 200%를 초과하면 고금리 국면에서 이자 비용 부담이 급증할 수 있습니다.
            * **유동/당좌비율**: 1년 안에 현금화할 수 있는 유동자산을 단기 부채로 나눈 수치로, 단기 자금 경색 위험을 피할 수 있는지 확인합니다.
            """)

    # 4. 수급
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
                st.success("🔥 **외인·기관 쌍끌이 순매수 구간**: 주가를 견인하는 메이저 주체들이 동반 매수 중으로 수급 모멘텀이 매우 우수합니다.")
            elif sum_f < 0 and sum_i < 0:
                st.error("🌧️ **외인·기관 동반 순매도 구간**: 메이저 주체들의 매도세로 인해 단기 주가 반등 탄력이 둔화될 수 있습니다.")
            elif sum_f > 0:
                st.info("💡 **외국인 주도 순매수**: 외국인 중심의 순매수가 주가를 지지하고 있습니다.")
            elif sum_i > 0:
                st.info("💡 **기관 주도 순매수**: 투신/연기금 등 국내 기관 자금이 유입 중입니다.")

            st.bar_chart(df_inv[["외국인(억원)", "기관(억원)"]])
            st.dataframe(df_inv, use_container_width=True)
        else:
            st.info("해외 서버 차단 또는 장 마감 집계 중으로 인해 세부 수급표를 불러오지 못했습니다. 가치평가 및 수익성 지표 탭을 확인해 주세요.")
