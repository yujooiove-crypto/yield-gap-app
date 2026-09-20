import streamlit as st
import yfinance as yf
import pandas as pd
from pykrx import stock
from datetime import datetime, timedelta

st.set_page_config(
    page_title="국내주식 종목별 주요지표 분석",
    page_icon="📊",
    layout="wide"
)

# --- 종목 매핑 캐싱 (국내 전종목 한글명 지원) ---
@st.cache_data(ttl=86400)
def get_krx_ticker_map():
    try:
        tickers = stock.get_market_ticker_list(market="ALL")
        mapping = {}
        for t in tickers:
            name = stock.get_market_ticker_name(t)
            mapping[name.lower()] = t
            mapping[name.replace(" ", "").lower()] = t
        return mapping
    except Exception:
        return {
            "삼성전자": "005930", "sk하이닉스": "000660", "현대차": "005380",
            "기아": "000270", "lg에너지솔루션": "373220", "삼성바이오로직스": "207940",
            "셀트리온": "068270", "kb금융": "105560", "신한지주": "055550",
            "포스코홀딩스": "005490", "posco홀딩스": "005490", "naver": "035420",
            "네이버": "035420", "카카오": "035720", "에코프로비엠": "247540",
            "에코프로": "086520", "알테오젠": "196170", "hlb": "028300"
        }

ticker_map = get_krx_ticker_map()

# --- 사이드바: 기준 금리 설정 ---
with st.sidebar:
    st.header("⚙️ 분석 기준 설정")
    deposit_rate = st.slider(
        "기준 예금 이자율 (무위험 금리, %)",
        min_value=1.0, max_value=10.0, value=3.5, step=0.1,
        help="일드갭(초과수익률) 산출 시 비교 기준이 되는 시중 정기예금/국고채 금리입니다."
    )
    st.info("💡 종목명(예: 현대차) 또는 6자리 코드(005380)를 입력하면 모든 지표와 수급이 자동 계산됩니다.")

# --- 메인 헤더 ---
st.title("📈 국내주식 종목별 주요지표 분석")
st.caption("가치평가 · 수익성 · 재무건전성 & 성장성 종합 진단 및 최근 10영업일 기관/외국인 수급 추이")

col_search, col_btn = st.columns([4, 1])
with col_search:
    search_query = st.text_input("종목명 또는 6자리 종목코드 입력", value="삼성전자", placeholder="예: 삼성전자, SK하이닉스, 005930")
with col_btn:
    st.write("")
    st.write("")
    run_btn = st.button("종목 분석", type="primary", use_container_width=True)

if run_btn or "analyzed_code" in st.session_state:
    if run_btn:
        query = search_query.strip()
        code = None
        # 1. 6자리 숫자 코드 판별
        if query.isdigit() and len(query) == 6:
            code = query
        else:
            q_clean = query.replace(" ", "").lower()
            code = ticker_map.get(q_clean) or ticker_map.get(query.lower())

        if not code:
            st.error(f"'{query}' 종목을 찾을 수 없습니다. 정확한 종목명이나 6자리 코드를 입력해 주세요.")
            st.stop()
        st.session_state["analyzed_code"] = code
    else:
        code = st.session_state["analyzed_code"]

    with st.spinner("한국거래소(KRX) 및 재무 데이터 분석 중..."):
        try:
            # 1. 기업 기본 정보 및 주가
            stock_name = stock.get_market_ticker_name(code)
            if not stock_name:
                stock_name = search_query

            today_str = datetime.today().strftime("%Y%m%d")
            start_fund = (datetime.today() - timedelta(days=10)).strftime("%Y%m%d")

            # KRX 기본 가치평가 지표 (PER, PBR, EPS, BPS, DIV)
            df_fund = stock.get_market_fundamental(start_fund, today_str, code)
            df_price = stock.get_market_ohlcv(start_fund, today_str, code)

            curr_price = int(df_price["종가"].iloc[-1]) if not df_price.empty else 0
            change_pct = float(df_price["등락률"].iloc[-1]) if not df_price.empty else 0.0

            krx_per = float(df_fund["PER"].iloc[-1]) if not df_fund.empty and "PER" in df_fund else None
            krx_pbr = float(df_fund["PBR"].iloc[-1]) if not df_fund.empty and "PBR" in df_fund else None
            krx_eps = float(df_fund["EPS"].iloc[-1]) if not df_fund.empty and "EPS" in df_fund else None
            krx_div = float(df_fund["DIV"].iloc[-1]) if not df_fund.empty and "DIV" in df_fund else None

            # 2. 보조 상세 재무지표 (ROE, 영업이익률, 부채비율, 유동비율, 성장성)
            yf_ticker = f"{code}.KS"
            stk = yf.Ticker(yf_ticker)
            info = stk.info
            if not info or not info.get("shortName"):
                yf_ticker = f"{code}.KQ"
                stk = yf.Ticker(yf_ticker)
                info = stk.info

            # 재무 비율 정리
            per_val = krx_per if (krx_per and krx_per > 0) else info.get("trailingPE")
            pbr_val = krx_pbr if (krx_pbr and krx_pbr > 0) else info.get("priceToBook")
            eps_val = krx_eps if krx_eps else info.get("trailingEps")
            div_val = krx_div if krx_div else (info.get("dividendYield", 0) * 100 if info.get("dividendYield") else 0.0)
            ev_ebitda = info.get("enterpriseToEbitda")

            roe_val = (info.get("returnOnEquity") * 100) if info.get("returnOnEquity") else (
                (pbr_val / per_val * 100) if (pbr_val and per_val and per_val > 0) else None
            )
            roa_val = (info.get("returnOnAssets") * 100) if info.get("returnOnAssets") else None
            op_margin = (info.get("operatingMargins") * 100) if info.get("operatingMargins") else None
            net_margin = (info.get("profitMargins") * 100) if info.get("profitMargins") else None

            debt_ratio = info.get("debtToEquity")
            curr_ratio = info.get("currentRatio")
            rev_growth = (info.get("revenueGrowth") * 100) if info.get("revenueGrowth") else None
            eps_growth = (info.get("earningsGrowth") * 100) if info.get("earningsGrowth") else None

            # 3. 최근 10영업일 수급 데이터 (기관/외국인/개인)
            start_investor = (datetime.today() - timedelta(days=25)).strftime("%Y%m%d")
            df_investor = stock.get_market_trading_value_by_date(start_investor, today_str, code)
            df_ohlcv = stock.get_market_ohlcv_by_date(start_investor, today_str, code)

        except Exception as e:
            st.error(f"데이터 조회 중 오류가 발생했습니다: {e}")
            st.stop()

    # --- 종목 개요 헤더 카드 ---
    st.divider()
    hdr_c1, hdr_c2, hdr_c3 = st.columns([2, 1, 1])
    with hdr_c1:
        st.subheader(f"🏢 {stock_name} ({code})")
    with hdr_c2:
        st.metric("현재가", f"{curr_price:,.0f}원", f"{change_pct:+.2f}%")
    with hdr_c3:
        market_label = "코스피 (KOSPI)" if yf_ticker.endswith(".KS") else "코스닥 (KOSDAQ)"
        st.write(f"**소속 시장:** `{market_label}`")

    # --- 탭 구성 (4개 영역) ---
    tab1, tab2, tab3, tab4 = st.tabs([
        "💰 1. 가치평가 지표",
        "📈 2. 수익성 지표",
        "🛡️ 3. 재무건전성 & 성장성",
        "👥 4. 최근 10영업일 수급 동향"
    ])

    # ==========================================
    # TAB 1: 가치평가 지표 (Valuation)
    # ==========================================
    with tab1:
        st.markdown("#### 기업 가치 대비 주가 수준 (Valuation)")
        st.write("주가가 기업이 벌어들이는 이익과 순자산에 비해 저평가되어 있는지, 배당 및 금리 대비 매력적인지 분석합니다.")

        # 일드갭 계산
        stock_yield = (1 / per_val * 100) if (per_val and per_val > 0) else 0
        yield_gap = (stock_yield - deposit_rate) if (per_val and per_val > 0) else None

        v_col1, v_col2, v_col3, v_col4 = st.columns(4)
        v_col1.metric("PER (주가수익비율)", f"{per_val:.1f}배" if per_val else "N/A", "15배 이하 저평가")
        v_col2.metric("PBR (주가순자산비율)", f"{pbr_val:.2f}배" if pbr_val else "N/A", "1.0배 이하 청산가치")
        v_col3.metric("EV/EBITDA", f"{ev_ebitda:.1f}배" if ev_ebitda else "N/A", "원금회수 소요기간")
        v_col4.metric("배당수익률", f"{div_val:.2f}%" if div_val else "0.00%", "3% 이상 안전마진")

        st.markdown("##### 📌 벤저민 그레이엄 일드갭(초과수익률) 진단")
        if yield_gap is not None:
            yg_c1, yg_c2, yg_c3 = st.columns(3)
            yg_c1.metric("주식 기대수익률 (1/PER)", f"{stock_yield:.2f}%")
            yg_c2.metric("기준 예금 이자율", f"{deposit_rate:.2f}%")
            yg_c3.metric("일드갭 (초과수익률)", f"{yield_gap:+.2f}%p")

            if yield_gap >= 4.0:
                st.success("🟢 **매우 유리 (주식 적극 매수 구간)**: 예금 대비 주식의 초과수익 보상이 4%p 이상으로 매우 매력적입니다.")
            elif yield_gap >= 2.0:
                st.info("🔵 **유리 (주식 비중 확대)**: 예금보다 2~4%p 높은 수익률이 기대되는 안정적 투자 구간입니다.")
            elif yield_gap >= 1.0:
                st.warning("🟡 **다소 유리 (선별적 접근)**: 예금 대비 초과수익이 1~2%p 수준으로 개별 성장성 검토가 필수입니다.")
            elif yield_gap >= 0.0:
                st.warning("🟠 **메리트 없음 (분산 권장)**: 주식 변동성 대비 기대보상이 적어 예금·채권 병행이 유리합니다.")
            else:
                st.error("🔴 **매우 불리 (예금 보유 유리)**: 주식 기대수익률이 무위험 예금 금리보다 낮습니다.")
        else:
            st.info("적자 기업이거나 PER 데이터가 없어 일드갭 진단을 생략합니다.")

        with st.expander("📖 가치평가 지표 상세 설명서"):
            st.markdown("""
            * **PER (주가수익비율)**: 현재 주가를 주당순이익(EPS)으로 나눈 값입니다. 시가총액만큼의 순이익을 벌어들이는 데 몇 년이 걸리는지 의미하며, 일반적으로 10~15배 이하일 때 저평가로 판단합니다.
            * **PBR (주가순자산비율)**: 현재 주가를 주당순자산(BPS)으로 나눈 값입니다. 1.0배 미만이면 기업이 당장 사업을 정리하고 자산을 분배했을 때 주가보다 순자산이 더 많다는 뜻(자산 저평가)입니다.
            * **EV/EBITDA**: 기업 전체 가치(시총+순차입금)를 영업현금창출능력으로 나눈 수치로, 감가상각비와 부채 영향을 제거한 실질 현금창출력 대비 주가 수준을 보여줍니다.
            * **일드갭 (초과수익률)**: 주식 기대수익률(1/PER)에서 국채나 은행 정기예금 금리를 뺀 값으로, 안전자산 대비 주식 투자의 프리미엄을 나타냅니다.
            """)

    # ==========================================
    # TAB 2: 수익성 지표 (Profitability)
    # ==========================================
    with tab2:
        st.markdown("#### 돈을 버는 효율성과 마진율 (Profitability)")
        st.write("주주와 기업의 자본을 투입해 얼마나 높은 비율의 영업이익과 순이익을 남겼는지 분석합니다.")

        p_col1, p_col2, p_col3, p_col4 = st.columns(4)
        p_col1.metric("ROE (자기자본이익률)", f"{roe_val:.1f}%" if roe_val else "N/A", "10% 이상 우량")
        p_col2.metric("ROA (총자산이익률)", f"{roa_val:.1f}%" if roa_val else "N/A", "자산 활용 효율")
        p_col3.metric("영업이익률", f"{op_margin:.1f}%" if op_margin else "N/A", "본업 경쟁력")
        p_col4.metric("당기순이익률", f"{net_margin:.1f}%" if net_margin else "N/A", "최종 마진")

        # 종합 진단
        if roe_val and roe_val >= 10:
            st.success(f"✅ **수익성 우수**: ROE가 `{roe_val:.1f}%`로 자기자본 대비 매우 훌륭한 복리 창출 능력을 보이고 있습니다.")
        elif roe_val and roe_val > 0:
            st.info(f"ℹ️ **수익성 보통**: ROE가 `{roe_val:.1f}%` 수준으로 시중 금리를 상회하나 고수익성 기업 대비 다소 완만합니다.")
        else:
            st.warning("⚠️ **수익성 주의**: 최근 분기/연간 순손실(적자)이 발생했거나 ROE 산정 데이터가 부족합니다.")

        with st.expander("📖 수익성 지표 상세 설명서"):
            st.markdown("""
            * **ROE (자기자본이익률)**: 주주의 순자본으로 1년간 얼마의 순이익을 창출했는지 측정하는 핵심 지표입니다. 워런 버핏은 연 15% 이상의 꾸준한 ROE를 유지하는 기업을 최고의 경제적 해자 기업으로 평가했습니다.
            * **ROA (총자산이익률)**: 부채를 포함한 총자산을 얼마나 효율적으로 굴려 이익을 냈는지 나타냅니다.
            * **영업이익률**: 매출액 중 순수 본업으로 남긴 영업이익의 비율입니다. 원가 통제력과 가격 결정력(해자)을 입증하는 척도입니다.
            * **당기순이익률**: 매출에서 각종 금융비용, 세금, 일회성 손익을 제외하고 주주 몫으로 최종 남은 순이익 비율입니다.
            """)

    # ==========================================
    # TAB 3: 재무건전성 & 성장성 (Stability & Growth)
    # ==========================================
    with tab3:
        st.markdown("#### 재무적 생존 체력과 사업 확장성 (Stability & Growth)")
        st.write("부도 위험 없이 위기를 견딜 수 있는 안정성과 매출·이익의 성장 추세를 분석합니다.")

        s_col1, s_col2, s_col3, s_col4 = st.columns(4)
        s_col1.metric("부채비율", f"{debt_ratio:.1f}%" if debt_ratio else "N/A", "100% 이하 안정권")
        s_col2.metric("유동비율", f"{curr_ratio * 100:.1f}%" if curr_ratio else "N/A", "150% 이상 권장")
        s_col3.metric("매출액 증가율 (YoY)", f"{rev_growth:+.1f}%" if rev_growth else "N/A", "외형 확장성")
        s_col4.metric("순이익 증가율 (YoY)", f"{eps_growth:+.1f}%" if eps_growth else "N/A", "실적 모멘텀")

        # 건전성 진단
        if debt_ratio and debt_ratio <= 100:
            st.success(f"✅ **재무 안정권**: 부채비율이 `{debt_ratio:.1f}%`로 재무구조가 매우 건전하며 금리 인상기 위험이 낮습니다.")
        elif debt_ratio and debt_ratio > 200:
            st.warning(f"⚠️ **부채비율 과다**: 부채비율이 `{debt_ratio:.1f}%`로 금융비용 부담이 클 수 있으므로 이자보상능력 점검이 필요합니다.")

        with st.expander("📖 재무건전성 및 성장성 지표 상세 설명서"):
            st.markdown("""
            * **부채비율**: 자기자본 대비 총부채의 비율입니다. 100% 이하가 가장 이상적이며, 200%를 초과하면 경기 침체기나 고금리 국면에서 유동성 리스크가 부각될 수 있습니다.
            * **유동비율**: 1년 안에 현금화할 수 있는 자산을 1년 안에 갚아야 할 단기 부채로 나눈 비율입니다. 150~200% 이상이어야 단기 자금 경색 위험을 피할 수 있습니다.
            * **매출액·순이익 증가율**: 전년 동기 대비 사업의 외형과 순이익이 커지고 있는지 확인하는 지표로, 주가의 중장기 우상향을 이끄는 핵심 원동력입니다.
            """)

    # ==========================================
    # TAB 4: 최근 10영업일 수급 동향 (기관/외국인)
    # ==========================================
    with tab4:
        st.markdown("#### 최근 10영업일 투자자별 순매수 동향")
        st.write("주가 흐름을 주도하는 외국인 투자자와 기관 투자자의 실질적인 수급 유입 현황입니다. (단위: 억원)")

        if df_investor is not None and not df_investor.empty:
            # 최근 10영업일 추출
            sub_inv = df_investor.tail(10).copy()
            sub_ohlcv = df_ohlcv.tail(10).copy()

            # 억원 단위로 환산
            trend_df = pd.DataFrame(index=sub_inv.index)
            trend_df["종가(원)"] = sub_ohlcv["종가"]
            trend_df["개인"] = (sub_inv["개인"] / 100000000).round(1)
            trend_df["외국인"] = (sub_inv["외국인합계"] / 100000000).round(1)
            trend_df["기관"] = (sub_inv["기관합계"] / 100000000).round(1)
            trend_df.index = trend_df.index.strftime("%Y-%m-%d")

            # 누적 순매수 합계
            sum_frg = trend_df["외국인"].sum()
            sum_inst = trend_df["기관"].sum()
            sum_ant = trend_df["개인"].sum()

            sq1, sq2, sq3 = st.columns(3)
            sq1.metric("10일간 외국인 누적 순매수", f"{sum_frg:+,.1f} 억원")
            sq2.metric("10일간 기관 누적 순매수", f"{sum_inst:+,.1f} 억원")
            sq3.metric("10일간 개인 누적 순매수", f"{sum_ant:+,.1f} 억원")

            # 수급 진단 코멘트
            if sum_frg > 0 and sum_inst > 0:
                st.success("🔥 **외인·기관 쌍끌이 순매수 구간**: 주가를 견인하는 메이저 주체들이 동반 매수세를 보이고 있어 수급 모멘텀이 매우 긍정적입니다.")
            elif sum_frg < 0 and sum_inst < 0:
                st.error("🌧️ **외인·기관 동반 순매도 구간**: 메이저 주체들의 차익 실현 및 매도세로 인해 단기 주가 상방이 제한될 수 있습니다.")
            elif sum_frg > 0:
                st.info("💡 **외국인 주도 순매수 국면**: 외국인 중심의 수급 유입이 지속되고 있습니다.")
            elif sum_inst > 0:
                st.info("💡 **기관 주도 순매수 국면**: 연기금/투신 등 국내 기관의 방어 및 매수세가 유입 중입니다.")

            # 일자별 수급 차트
            st.markdown("##### 📊 일자별 외국인 / 기관 순매수 추이 (억원)")
            chart_data = trend_df[["외국인", "기관"]]
            st.bar_chart(chart_data)

            # 세부 수급 데이터 테이블
            st.markdown("##### 📋 일자별 세부 수급 내역")
            st.dataframe(
                trend_df[["종가(원)", "외국인", "기관", "개인"]].sort_index(ascending=False),
                use_container_width=True
            )
        else:
            st.warning("최근 수급 데이터를 불러오지 못했습니다. 장 마감 후 또는 거래일 여부를 확인해 주세요.")
