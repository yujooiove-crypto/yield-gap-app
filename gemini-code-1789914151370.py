import streamlit as st
import yfinance as yf
import pandas as pd

st.set_page_config(
    page_title="국내주식 종목별 주요지표 분석",
    page_icon="📊",
    layout="wide"
)

# 1. 국내 대표 코스피 / 코스닥 상장사 150+ 종목 마스터 사전
KRX_STOCKS = {
    # 반도체 / IT 부품
    "005930": "삼성전자", "005935": "삼성전자우", "000660": "SK하이닉스", "042700": "한미반도체",
    "403870": "HPSP", "058470": "리노공업", "000990": "DB하이텍", "039030": "이오테크닉스",
    "240810": "원익IPS", "095340": "ISC", "067310": "하나마이크론", "036930": "주성엔지니어링",
    "357780": "솔브레인", "005290": "동진쎄미켐", "084370": "유진테크", "089030": "테크윙",
    "003160": "디아이", "459580": "에이직랜드", "394280": "오픈엣지테크놀로지", "080220": "제주반도체",
    "054450": "텔레칩스", "399720": "가온칩스", "036540": "SFA반도체", "018260": "삼성에스디에스",
    # 2차전지 / 소재 / 철강
    "373220": "LG에너지솔루션", "006400": "삼성SDI", "051910": "LG화학", "005490": "POSCO홀딩스",
    "003670": "포스코퓨처엠", "247540": "에코프로비엠", "086520": "에코프로", "450080": "에코프로머티",
    "066970": "엘앤에프", "348370": "엔켐", "005070": "코스모신소재", "011780": "금양",
    "010130": "고려아연", "004020": "현대제철", "103140": "풍산", "047050": "포스코인터내셔널",
    # 자동차 / 모빌리티 / 항공 / 해운
    "005380": "현대차", "005385": "현대차우", "000270": "기아", "012330": "현대모비스",
    "018880": "한온시스템", "011210": "현대위아", "204320": "HL만도", "161390": "한국타이어앤테크놀로지",
    "003490": "대한항공", "020560": "아시아나항공", "011200": "HMM", "028670": "팬오션", "000120": "CJ대한통운",
    # 제약 / 바이오 / 헬스케어
    "207940": "삼성바이오로직스", "068270": "셀트리온", "196170": "알테오젠", "028300": "HLB",
    "000250": "삼천당제약", "000100": "유한양행", "128940": "한미약품", "008930": "한미사이언스",
    "141080": "리가켐바이오", "298380": "에이비엘바이오", "068760": "셀트리온제약", "087010": "펩트론",
    "310210": "보로노이", "328130": "루닛", "096530": "씨젠", "069620": "대웅제약", "185750": "종근당",
    "006280": "녹십자", "145020": "휴젤", "086900": "메디톡스", "302440": "SK바이오사이언스", "326030": "SK바이오팜",
    # 인터넷 / 플랫폼 / 게임 / 엔터
    "035420": "NAVER", "035720": "카카오", "323410": "카카오뱅크", "377300": "카카오페이",
    "259960": "크래프톤", "036570": "엔씨소프트", "251270": "넷마블", "263750": "펄어비스", "112040": "위메이드",
    "352820": "하이브", "035900": "JYP Ent.", "041510": "에스엠", "122870": "와이지엔터테인먼트", "035760": "CJ ENM",
    # 금융 / 지주
    "105560": "KB금융", "055550": "신한지주", "086790": "하나금융지주", "316140": "우리금융지주",
    "138040": "메리츠금융지주", "024110": "기업은행", "032830": "삼성생명", "000810": "삼성화재",
    "005830": "DB손해보험", "039490": "키움증권", "006800": "미래에셋증권", "071050": "한국금융지주",
    "016360": "삼성증권", "005940": "NH투자증권",
    # 방산 / 조선 / 중공업 / 전력 / 기계
    "034020": "두산에너빌리티", "454910": "두산로보틱스", "042670": "두산밥캣", "012450": "한화에어로스페이스",
    "042660": "한화오션", "047810": "한국항공우주", "079550": "LIG넥스원", "064350": "현대로템",
    "329180": "HD현대중공업", "009540": "HD한국조선해양", "010620": "HD현대미포", "267250": "HD현대일렉트릭",
    "298040": "효성중공업", "010120": "LS ELECTRIC", "006260": "LS", "010140": "삼성중공업",
    # 음식료 / 소비재 / 유통 / 통신 / 유틸리티
    "003230": "삼양식품", "004370": "농심", "007310": "오뚜기", "097950": "CJ제일제당",
    "005300": "롯데칠성", "000080": "하이트진로", "090430": "아모레퍼시픽", "051900": "LG생활건강",
    "192820": "코스맥스", "161890": "한국콜마", "383220": "F&F", "028260": "삼성물산",
    "069960": "현대백화점", "023530": "롯데쇼핑", "139480": "이마트", "017670": "SK텔레콤",
    "030200": "KT", "032640": "LG유플러스", "015760": "한국전력", "036460": "한국가스공사",
    "033780": "KT&G", "035250": "강원랜드", "096770": "SK이노베이션", "010950": "S-Oil",
    "078930": "GS", "011170": "롯데케미칼", "277810": "레인보우로보틱스", "066570": "LG전자"
}

# 이름순 정렬된 자동완성 옵션 목록
SORTED_OPTIONS = sorted([f"{name} ({code})" for code, name in KRX_STOCKS.items()])

# 2. 글로벌 금융망 데이터 조회 및 PER/PBR 역산 함수
@st.cache_data(ttl=300)
def fetch_stock_data(code, stock_name):
    data = {
        "code": code, "name": stock_name, "market": "코스피",
        "price": 0, "change_pct": 0.0,
        "per": None, "fwd_per": None, "pbr": None, "div_yield": None,
        "roe": None, "op_margin": None, "net_margin": None,
        "debt_ratio": None, "curr_ratio": None, "rev_growth": None
    }

    # 코스피(.KS) -> 코스닥(.KQ) 순차 탐색
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

    # 주가 및 등락률
    curr_p = info.get("currentPrice") or info.get("regularMarketPrice") or info.get("previousClose") or 0
    data["price"] = int(curr_p)
    prev_p = info.get("previousClose")
    if prev_p and data["price"]:
        data["change_pct"] = round(((data["price"] - prev_p) / prev_p) * 100, 2)

    # 1) PER 산출 (제공 필드 -> 주가 / EPS 직접 계산)
    per = info.get("trailingPE")
    eps = info.get("trailingEps")
    if per and per > 0:
        data["per"] = round(float(per), 1)
    elif eps and eps > 0 and data["price"] > 0:
        data["per"] = round(data["price"] / eps, 1)

    fwd_pe = info.get("forwardPE")
    fwd_eps = info.get("forwardEps")
    if fwd_pe and fwd_pe > 0:
        data["fwd_per"] = round(float(fwd_pe), 1)
    elif fwd_eps and fwd_eps > 0 and data["price"] > 0:
        data["fwd_per"] = round(data["price"] / fwd_eps, 1)

    # 2) PBR 산출 (제공 필드 -> 주가 / BPS 직접 계산)
    pbr = info.get("priceToBook")
    bv = info.get("bookValue")
    if pbr and pbr > 0:
        data["pbr"] = round(float(pbr), 2)
    elif bv and bv > 0 and data["price"] > 0:
        data["pbr"] = round(data["price"] / bv, 2)

    # 3) 배당수익률
    dy = info.get("dividendYield")
    if dy is not None:
        data["div_yield"] = round(float(dy) * 100 if float(dy) < 0.2 else float(dy), 2)

    # 4) ROE (제공 수치 -> PBR / PER 공준 공식 역산)
    roe = info.get("returnOnEquity")
    if roe is not None:
        data["roe"] = round(float(roe) * 100 if abs(float(roe)) < 2.0 else float(roe), 1)
    elif data["pbr"] and data["per"] and data["per"] > 0:
        data["roe"] = round((data["pbr"] / data["per"]) * 100, 1)

    # 5) 마진율 및 재무건전성
    opm = info.get("operatingMargins")
    if opm is not None:
        data["op_margin"] = round(float(opm) * 100 if abs(float(opm)) < 2.0 else float(opm), 1)

    npm = info.get("profitMargins")
    if npm is not None:
        data["net_margin"] = round(float(npm) * 100 if abs(float(npm)) < 2.0 else float(npm), 1)

    debt = info.get("debtToEquity")
    if debt is not None:
        data["debt_ratio"] = round(float(debt), 1)

    curr = info.get("currentRatio")
    if curr is not None:
        cr = float(curr)
        data["curr_ratio"] = round(cr * 100 if cr < 10.0 else cr, 1)

    rg = info.get("revenueGrowth")
    if rg is not None:
        data["rev_growth"] = round(float(rg) * 100, 1)

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

# --- 메인 화면 헤더 ---
st.title("📈 국내주식 종목별 주요지표 분석")
st.caption("가치평가 · 수익성 · 재무건전성 종합 진단 (차단 없는 내장 검색 시스템)")

# 인기 종목 바로가기
st.write("🔥 **인기 종목 빠른 선택:**")
btn_cols = st.columns(7)
popular_picks = ["삼성전자", "SK하이닉스", "현대차", "알테오젠", "삼양식품", "루닛", "셀트리온"]
for i, pick in enumerate(popular_picks):
    if btn_cols[i].button(pick, use_container_width=True):
        st.session_state["chosen_stock"] = pick

# 검색 방식 선택 (라디오)
search_mode = st.radio(
    "검색 방식을 선택하세요:",
    ["🔍 종목명으로 찾기 (한글 자동완성 검색)", "🔢 6자리 종목코드 직접 입력"],
    horizontal=True
)

target_code, target_name = "005930", "삼성전자"

if search_mode.startswith("🔍"):
    # 기본값 설정
    default_kw = st.session_state.get("chosen_stock", "삼성전자")
    default_idx = 0
    for idx, opt in enumerate(SORTED_OPTIONS):
        if opt.startswith(default_kw):
            default_idx = idx
            break

    selected_item = st.selectbox(
        "종목명을 입력하면 목록이 즉시 필터링됩니다 (예: 삼양, 루닛, 현대, 하이브 등 입력):",
        options=SORTED_OPTIONS,
        index=default_idx
    )
    target_code = selected_item.split("(")[-1].replace(")", "").strip()
    target_name = selected_item.split("(")[0].strip()

else:
    direct_code = st.text_input("6자리 종목코드 입력 (예: 005930, 003230)", value="005930")
    target_code = direct_code.strip()
    target_name = KRX_STOCKS.get(target_code, f"종목 {target_code}")

run_analysis = st.button("종목 분석 실행", type="primary", use_container_width=True)

if run_analysis or "analyzed_code" not in st.session_state or st.session_state.get("analyzed_code") != target_code:
    st.session_state["analyzed_code"] = target_code

    with st.spinner(f"'{target_name}' ({target_code}) 금융 데이터를 실시간 집계 중입니다..."):
        d = fetch_stock_data(target_code, target_name)

    if not d or d["price"] == 0:
        st.error(f"'{target_name}' ({target_code}) 종목의 시세 정보를 불러올 수 없습니다. 코드를 확인해 주세요.")
    else:
        st.divider()
        h1, h2, h3 = st.columns([2, 1, 1])
        h1.subheader(f"🏢 {d['name']} ({d['code']})")
        h2.metric("현재 주가", f"{d['price']:,.0f}원", f"{d['change_pct']:+.2f}%" if d['change_pct'] != 0 else "")
        h3.write(f"**소속 시장:** `{d['market']}`")

        tab1, tab2, tab3 = st.tabs([
            "💰 1. 가치평가 지표 (일드갭)",
            "📈 2. 수익성 지표",
            "🛡️ 3. 재무건전성 & 성장성 지표"
        ])

        # TAB 1: 가치평가
        with tab1:
            st.markdown("#### 기업 가치 대비 주가 수준 (Valuation)")
            v1, v2, v3, v4 = st.columns(4)
            v1.metric("PER (주가수익비율)", f"{d['per']:.1f}배" if d['per'] else "적자 기업", "15배 이하 저평가")
            v2.metric("PBR (순자산비율)", f"{d['pbr']:.2f}배" if d['pbr'] else "N/A", "1.0배 이하 청산가치")
            v3.metric("선행 PER (추정)", f"{d['fwd_per']:.1f}배" if d['fwd_per'] else (f"{d['per']:.1f}배" if d['per'] else "N/A"), "컨센서스 기준")
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
                    st.success("🟢 **매우 유리 (주식 적극 매수 구간)** — 예금 금리 대비 주식 초과수익 보상이 4%p 이상으로 기대수익이 매우 높습니다.")
                elif yield_gap >= 2.0:
                    st.info("🔵 **유리 (주식 비중 확대)** — 예금보다 2~4%p 높은 수익률이 기대되는 안정적 투자 구간입니다.")
                elif yield_gap >= 1.0:
                    st.warning("🟡 **다소 유리 (선별 투자)** — 예금 대비 1~2%p 초과수익 구간으로 실적 점검이 필요합니다.")
                elif yield_gap >= 0.0:
                    st.warning("🟠 **메리트 없음 (분산 권장)** — 주식 위험 대비 보상이 적어 예금·채권 병행이 유리합니다.")
                else:
                    st.error("🔴 **매우 불리 (예금 보유 유리)** — 주식 기대수익률이 무위험 예금 금리보다 낮습니다.")
            else:
                st.info("당기순손실(적자) 기업이거나 PER 산출이 불가능하여 일드갭 계산을 생략합니다.")

            with st.expander("📖 가치평가 지표 상세 설명"):
                st.markdown("""
                * **PER (주가수익비율)**: 현재 주가를 1주당 순이익(EPS)으로 나눈 값으로 낮을수록 이익 대비 저평가 상태입니다.
                * **PBR (주가순자산비율)**: 주가를 1주당 순자산(BPS)으로 나눈 수치로 1.0배 미만이면 순자산 청산가치보다 쌉니다.
                * **일드갭 (Yield Gap)**: 주식 기대수익률(1/PER)에서 은행 예금/국채 금리를 뺀 초과수익률로 안전자산 대비 주식의 보상 매력도를 측정합니다.
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
                * **영업이익률**: 매출액 중 원가와 판관비를 제하고 남은 순수 본업의 영업이익 비율로, 브랜드 가격 결정력을 증명합니다.
                * **순이익률**: 금융비용과 법인세까지 모두 제하고 최종 주주 몫으로 남은 순이익 비율입니다.
                """)

        # TAB 3: 재무건전성 & 성장성
        with tab3:
            st.markdown("#### 재무적 생존 체력과 사업 확장성 (Stability & Growth)")
            s1, s2, s3 = st.columns(3)
            s1.metric("부채비율", f"{d['debt_ratio']:.1f}%" if d['debt_ratio'] is not None else "N/A", "100% 이하 안정권")
            s2.metric("유동비율", f"{d['curr_ratio']:.1f}%" if d['curr_ratio'] is not None else "N/A", "100% 이상 권장")
            s3.metric("매출 증가율 (YoY)", f"{d['rev_growth']:+.1f}%" if d['rev_growth'] is not None else "N/A", "외형 성장")

            if d['debt_ratio'] is not None and d['debt_ratio'] <= 100:
                st.success(f"✅ **재무구조 우량**: 부채비율이 `{d['debt_ratio']:.1f}%`로 고금리 국면에서도 매우 안전합니다.")
            elif d['debt_ratio'] is not None:
                st.warning(f"⚠️ **부채비율 점검**: 부채비율이 `{d['debt_ratio']:.1f}%`로 업종 특성 및 금융비용을 점검해야 합니다.")

            with st.expander("📖 재무건전성 및 성장성 지표 상세 설명"):
                st.markdown("""
                * **부채비율**: 자기자본 대비 총부채 비율입니다. 100% 이하가 이상적이며, 낮을수록 재무 안정성이 높습니다.
                * **유동비율**: 1년 안에 현금화할 수 있는 유동자산으로 단기 부채를 갚을 수 있는 능력(100% 이상 권장)입니다.
                * **매출 증가율**: 전년 동기 대비 기업의 외형 확장 속도를 보여주는 핵심 성장 지표입니다.
                """)
