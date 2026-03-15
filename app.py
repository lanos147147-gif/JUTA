import re
import html
import requests
import numpy as np
import pandas as pd
import streamlit as st
import yfinance as yf
import ta

from plotly.subplots import make_subplots
import plotly.graph_objects as go
from streamlit_autorefresh import st_autorefresh

st.set_page_config(
    page_title="주타,주식하다 현타올때",
    page_icon="📈",
    layout="wide"
)

# =========================
# 스타일
# =========================
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;700;800&family=Noto+Sans+KR:wght@400;500;700;800&display=swap');

html, body, [class*="css"] {
    font-family: 'Inter', 'Noto Sans KR', sans-serif;
}

.stApp {
    background: linear-gradient(180deg, #fff8fb 0%, #f7faff 45%, #eef4ff 100%);
    color: #1f2937;
}

.block-container {
    padding-top: 1.1rem;
    padding-bottom: 2rem;
}

.main-card {
    background: linear-gradient(135deg, #8b5cf6 0%, #3b82f6 100%);
    border-radius: 24px;
    padding: 28px 30px;
    color: white;
    box-shadow: 0 18px 40px rgba(59, 130, 246, 0.25);
    margin-bottom: 18px;
}

.sub-card {
    background: rgba(255,255,255,0.88);
    border: 1px solid rgba(255,255,255,0.75);
    backdrop-filter: blur(12px);
    border-radius: 22px;
    padding: 18px;
    box-shadow: 0 12px 30px rgba(148, 163, 184, 0.18);
}

.badge {
    padding: 14px 18px;
    border-radius: 18px;
    font-size: 24px;
    font-weight: 800;
    text-align: center;
    margin: 8px 0 14px 0;
}

.buy-strong { background: #dcfce7; color: #166534; border: 1px solid #86efac; }
.buy { background: #dbeafe; color: #1d4ed8; border: 1px solid #93c5fd; }
.hold { background: #fef3c7; color: #92400e; border: 1px solid #fcd34d; }
.sell { background: #fee2e2; color: #b91c1c; border: 1px solid #fca5a5; }
.sell-strong { background: #fce7f3; color: #be185d; border: 1px solid #f9a8d4; }

.news-good {
    display: inline-block;
    padding: 6px 10px;
    border-radius: 999px;
    background: #dcfce7;
    color: #166534;
    font-weight: 700;
    font-size: 12px;
}

.news-bad {
    display: inline-block;
    padding: 6px 10px;
    border-radius: 999px;
    background: #fee2e2;
    color: #b91c1c;
    font-weight: 700;
    font-size: 12px;
}

.news-neutral {
    display: inline-block;
    padding: 6px 10px;
    border-radius: 999px;
    background: #e5e7eb;
    color: #374151;
    font-weight: 700;
    font-size: 12px;
}

div[data-testid="stMetric"] {
    background: rgba(255,255,255,0.92);
    border: 1px solid rgba(226,232,240,1);
    border-radius: 18px;
    padding: 10px 14px;
    box-shadow: 0 8px 20px rgba(148, 163, 184, 0.12);
}

section[data-testid="stSidebar"] {
    background: linear-gradient(180deg, #f8fbff 0%, #f4f0ff 100%);
}

.small-note {
    color: #64748b;
    font-size: 13px;
}
</style>
""", unsafe_allow_html=True)

st.markdown("""
<div class="main-card">
    <div style="font-size:34px;font-weight:800;">📊 차트 도우미</div>
    <div style="font-size:16px;opacity:0.95;margin-top:6px;">
        미국주식 전용 · 실시간에 가까운 분봉 · RSI · MACD · 이평선 · 볼린저밴드 · 엔벨로프 · 뉴스 호재/악재
    </div>
</div>
""", unsafe_allow_html=True)

# =========================
# 유틸
# =========================
def safe_num(v, nd=2, suffix=""):
    try:
        if pd.isna(v):
            return "N/A"
        return f"{float(v):,.{nd}f}{suffix}"
    except Exception:
        return "N/A"

def strip_html_tags(text):
    if text is None:
        return ""
    text = re.sub(r"<[^>]+>", "", str(text))
    text = html.unescape(text)
    return text.strip()

# =========================
# 미국 종목 검색
# =========================
@st.cache_data(ttl=600)
def search_us_symbols(query: str):
    if not query:
        return []

    url = "https://query2.finance.yahoo.com/v1/finance/search"
    params = {
        "q": query,
        "quotesCount": 12,
        "newsCount": 0,
        "lang": "en-US",
        "region": "US"
    }
    headers = {"User-Agent": "Mozilla/5.0"}

    try:
        r = requests.get(url, params=params, headers=headers, timeout=10)
        r.raise_for_status()
        data = r.json()
    except Exception:
        return []

    out = []
    for q in data.get("quotes", []):
        symbol = q.get("symbol")
        if not symbol:
            continue

        quote_type = q.get("quoteType", "")
        if quote_type not in ["EQUITY", "ETF"]:
            continue

        name = q.get("shortname") or q.get("longname") or symbol
        exch = q.get("exchange") or q.get("exchDisp") or ""

        out.append({
            "ticker": symbol,
            "name": name,
            "market": exch,
            "yf_symbol": symbol,
            "label": f"{name} ({symbol}) · {exch}"
        })

    return out

# =========================
# 가격 데이터
# =========================
@st.cache_data(ttl=120)
def fetch_yf_history(symbol: str, period="6mo", interval="1d"):
    try:
        tk = yf.Ticker(symbol)
        df = tk.history(period=period, interval=interval, auto_adjust=False)
        if df is None or df.empty:
            return pd.DataFrame()
        return df.rename(columns=str.title)
    except Exception:
        return pd.DataFrame()

@st.cache_data(ttl=300)
def fetch_info(symbol: str):
    try:
        info = yf.Ticker(symbol).info
        return info if isinstance(info, dict) else {}
    except Exception:
        return {}

# =========================
# 뉴스
# =========================
@st.cache_data(ttl=600)
def fetch_yahoo_news(query: str):
    if not query:
        return []

    url = "https://query2.finance.yahoo.com/v1/finance/search"
    params = {
        "q": query,
        "quotesCount": 0,
        "newsCount": 8,
        "lang": "en-US",
        "region": "US"
    }
    headers = {"User-Agent": "Mozilla/5.0"}

    try:
        r = requests.get(url, params=params, headers=headers, timeout=10)
        r.raise_for_status()
        data = r.json()
    except Exception:
        return []

    items = []
    for item in data.get("news", []):
        title = item.get("title") or item.get("content", {}).get("title") or "제목 없음"
        publisher = item.get("publisher") or "Yahoo"
        link = item.get("link") or item.get("clickThroughUrl", {}).get("url") or ""

        items.append({
            "title": strip_html_tags(title),
            "description": "",
            "link": link,
            "publisher": publisher
        })

    return items

# =========================
# 감정분석
# =========================
POSITIVE_KEYWORDS = [
    "beats", "surge", "rally", "upgrade", "profit", "growth", "record",
    "strong", "gain", "bullish", "expands", "jump", "rise", "positive",
    "approval", "partnership", "contract", "buyback", "outperform"
]

NEGATIVE_KEYWORDS = [
    "misses", "plunge", "downgrade", "loss", "lawsuit", "risk",
    "weak", "drop", "fall", "bearish", "decline", "probe", "recall",
    "delay", "cuts", "warning", "negative", "selloff"
]

def keyword_sentiment_score(text: str):
    t = str(text).lower()
    score = 0.0

    for k in POSITIVE_KEYWORDS:
        if k in t:
            score += 1.0

    for k in NEGATIVE_KEYWORDS:
        if k in t:
            score -= 1.0

    if score > 0:
        return min(score / 3.0, 1.0)
    if score < 0:
        return max(score / 3.0, -1.0)
    return 0.0

def score_to_tag(score):
    if score >= 0.15:
        return "호재", "news-good"
    if score <= -0.15:
        return "악재", "news-bad"
    return "중립", "news-neutral"

# =========================
# 보조지표
# =========================
def add_indicators(df: pd.DataFrame):
    x = df.copy()

    x["SMA20"] = ta.trend.sma_indicator(x["Close"], window=20)
    x["SMA60"] = ta.trend.sma_indicator(x["Close"], window=60)
    x["EMA20"] = ta.trend.ema_indicator(x["Close"], window=20)

    macd = ta.trend.MACD(x["Close"])
    x["MACD"] = macd.macd()
    x["MACD_SIGNAL"] = macd.macd_signal()
    x["MACD_HIST"] = macd.macd_diff()

    x["RSI"] = ta.momentum.rsi(x["Close"], window=14)

    bb = ta.volatility.BollingerBands(x["Close"], window=20, window_dev=2)
    x["BB_UPPER"] = bb.bollinger_hband()
    x["BB_MIDDLE"] = bb.bollinger_mavg()
    x["BB_LOWER"] = bb.bollinger_lband()

    x["ENV_UPPER"] = x["SMA20"] * 1.03
    x["ENV_LOWER"] = x["SMA20"] * 0.97

    x["VOL_MA20"] = x["Volume"].rolling(20).mean()
    x["VOL_RATIO"] = x["Volume"] / x["VOL_MA20"]

    slope = x["SMA20"].diff(5) / 5
    x["ANGLE"] = np.degrees(np.arctan(slope.fillna(0)))

    return x

def finalize_indicator_df(df: pd.DataFrame):
    if df is None or df.empty:
        return pd.DataFrame()

    x = add_indicators(df)

    need_cols = [
        "RSI", "MACD", "MACD_SIGNAL", "SMA20", "SMA60",
        "BB_UPPER", "BB_LOWER", "ENV_UPPER", "ENV_LOWER",
        "VOL_RATIO", "ANGLE"
    ]
    x = x.dropna(subset=need_cols)
    return x

def evaluate_signal(df: pd.DataFrame, news_score: float = 0.0):
    latest = df.iloc[-1]
    prev = df.iloc[-2] if len(df) > 1 else latest

    score = 0
    reasons = []

    if latest["RSI"] < 30:
        score += 2
        reasons.append("RSI 과매도")
    elif latest["RSI"] < 40:
        score += 1
        reasons.append("RSI 낮은 구간")
    elif latest["RSI"] > 70:
        score -= 2
        reasons.append("RSI 과매수")
    elif latest["RSI"] > 60:
        score -= 1
        reasons.append("RSI 높은 구간")

    if latest["MACD"] > latest["MACD_SIGNAL"]:
        score += 1.5
        reasons.append("MACD 상향")
    else:
        score -= 1.5
        reasons.append("MACD 하향")

    if latest["Close"] > latest["SMA20"]:
        score += 1
        reasons.append("종가가 20일선 위")
    else:
        score -= 1
        reasons.append("종가가 20일선 아래")

    if latest["Close"] > latest["SMA60"]:
        score += 1
        reasons.append("중기 추세 양호")
    else:
        score -= 1
        reasons.append("중기 추세 약함")

    if latest["VOL_RATIO"] > 1.5:
        score += 1
        reasons.append("거래량 증가")
    elif latest["VOL_RATIO"] < 0.8:
        score -= 0.5
        reasons.append("거래량 약함")

    if latest["Close"] < latest["BB_LOWER"]:
        score += 1
        reasons.append("볼린저 하단 근처")
    elif latest["Close"] > latest["BB_UPPER"]:
        score -= 1
        reasons.append("볼린저 상단 근처")

    if latest["Close"] < latest["ENV_LOWER"]:
        score += 0.5
        reasons.append("엔벨로프 하단")
    elif latest["Close"] > latest["ENV_UPPER"]:
        score -= 0.5
        reasons.append("엔벨로프 상단")

    if latest["ANGLE"] > 10:
        score += 0.5
        reasons.append("이평선 기울기 상승")
    elif latest["ANGLE"] < -10:
        score -= 0.5
        reasons.append("이평선 기울기 하락")

    if latest["Close"] > prev["Close"]:
        score += 0.5
        reasons.append("단기 흐름 상승")
    else:
        score -= 0.5
        reasons.append("단기 흐름 약세")

    if news_score >= 0.15:
        score += 0.5
        reasons.append("뉴스 호재 우세")
    elif news_score <= -0.15:
        score -= 0.5
        reasons.append("뉴스 악재 우세")

    if score >= 4:
        return "강력매수", "buy-strong", score, reasons
    elif score >= 2:
        return "매수", "buy", score, reasons
    elif score > -2:
        return "관망", "hold", score, reasons
    elif score > -4:
        return "매도", "sell", score, reasons
    else:
        return "강력매도", "sell-strong", score, reasons

# =========================
# 사이드바
# =========================
st.sidebar.markdown("## 🎀 메뉴")
auto_refresh = st.sidebar.toggle("자동 새로고침", value=True)
refresh_sec = st.sidebar.slider("새로고침(초)", 10, 120, 30, 10)
show_intraday = st.sidebar.toggle("실시간에 가까운 분봉 차트", value=True)
intraday_interval = st.sidebar.selectbox("분봉 간격", ["1m", "5m", "15m"], index=0)
daily_period = st.sidebar.selectbox("일봉 분석 기간", ["3mo", "6mo", "1y", "2y"], index=1)

st.markdown("### 🇺🇸 미국주식")
us_keyword = st.sidebar.text_input("미국 종목 검색", value="Apple")

if auto_refresh:
    st_autorefresh(interval=refresh_sec * 1000, key="refresh_key")

us_results = search_us_symbols(us_keyword)

if us_results:
    choice = st.selectbox("종목 선택", [x["label"] for x in us_results], index=0)
    selected = next(x for x in us_results if x["label"] == choice)
    display_name = f"{selected['name']} ({selected['ticker']})"
    yf_symbol = selected["yf_symbol"]
    news_query = selected["name"]
else:
    manual = st.text_input("직접 티커 입력", value="AAPL")
    display_name = manual
    yf_symbol = manual
    news_query = manual

st.toast(f"{display_name} 불러오는 중", icon="✨")

# =========================
# 시세 로드
# =========================
daily_df = fetch_yf_history(yf_symbol, period=daily_period, interval="1d")

if daily_df.empty:
    st.error("가격 데이터를 불러오지 못했습니다.")
    st.stop()

chart_df = daily_df.copy()
chart_note = "일봉 기반 분석"

if show_intraday:
    intraday_df = fetch_yf_history(yf_symbol, period="5d", interval=intraday_interval)
    if intraday_df is not None and not intraday_df.empty:
        chart_df = intraday_df.copy()
        chart_note = f"{intraday_interval} 자동 새로고침 차트"

daily_ind = finalize_indicator_df(daily_df)
chart_ind = finalize_indicator_df(chart_df)

if daily_ind.empty:
    st.error("보조지표 계산에 필요한 데이터가 부족합니다.")
    st.stop()

if chart_ind.empty:
    chart_ind = daily_ind.copy()

# =========================
# 뉴스 로드
# =========================
news_items = fetch_yahoo_news(news_query)

scored_news = []
scores = []

for item in news_items:
    title = item.get("title", "")
    score = keyword_sentiment_score(title)
    tag, tag_class = score_to_tag(score)
    scores.append(score)

    scored_news.append({
        "title": title,
        "description": item.get("description", ""),
        "link": item.get("link", ""),
        "publisher": item.get("publisher", ""),
        "tag": tag,
        "tag_class": tag_class,
        "score": score
    })

avg_news = float(np.mean(scores)) if scores else 0.0

# =========================
# 종합 평가
# =========================
signal, signal_class, signal_score, reasons = evaluate_signal(daily_ind, avg_news)

latest = daily_ind.iloc[-1]
prev_close = daily_ind.iloc[-2]["Close"] if len(daily_ind) > 1 else latest["Close"]
chg_pct = ((latest["Close"] / prev_close) - 1) * 100 if prev_close else 0.0

# =========================
# 상단 카드
# =========================
st.markdown(f"""
<div class="sub-card">
    <div style="font-size:28px;font-weight:800;">{display_name}</div>
    <div class="small-note">{chart_note}</div>
</div>
""", unsafe_allow_html=True)

st.markdown(
    f"""<div class="badge {signal_class}">🤖 종합 평가: {signal} · 점수 {signal_score:.1f}</div>""",
    unsafe_allow_html=True
)

m1, m2, m3, m4, m5 = st.columns(5)
m1.metric("현재가", safe_num(latest["Close"]))
m2.metric("등락률", safe_num(chg_pct, 2, "%"))
m3.metric("RSI", safe_num(latest["RSI"]))
m4.metric("MACD", safe_num(latest["MACD"], 3))
m5.metric("거래량비", safe_num(latest["VOL_RATIO"], 2, "x"))

# =========================
# 차트
# =========================
fig = make_subplots(
    rows=4, cols=1, shared_xaxes=True, vertical_spacing=0.04,
    row_heights=[0.55, 0.15, 0.15, 0.15],
    subplot_titles=("가격 차트", "거래량", "RSI", "MACD")
)

fig.add_trace(
    go.Candlestick(
        x=chart_ind.index,
        open=chart_ind["Open"],
        high=chart_ind["High"],
        low=chart_ind["Low"],
        close=chart_ind["Close"],
        name="가격"
    ),
    row=1, col=1
)

fig.add_trace(go.Scatter(x=chart_ind.index, y=chart_ind["SMA20"], name="SMA20", line=dict(color="#2563eb", width=2)), row=1, col=1)
fig.add_trace(go.Scatter(x=chart_ind.index, y=chart_ind["SMA60"], name="SMA60", line=dict(color="#f59e0b", width=2)), row=1, col=1)
fig.add_trace(go.Scatter(x=chart_ind.index, y=chart_ind["EMA20"], name="EMA20", line=dict(color="#10b981", width=2)), row=1, col=1)
fig.add_trace(go.Scatter(x=chart_ind.index, y=chart_ind["BB_UPPER"], name="볼밴 상단", line=dict(color="#8b5cf6", dash="dot")), row=1, col=1)
fig.add_trace(go.Scatter(x=chart_ind.index, y=chart_ind["BB_LOWER"], name="볼밴 하단", line=dict(color="#8b5cf6", dash="dot")), row=1, col=1)
fig.add_trace(go.Scatter(x=chart_ind.index, y=chart_ind["ENV_UPPER"], name="엔벨로프 상단", line=dict(color="#ec4899", dash="dash")), row=1, col=1)
fig.add_trace(go.Scatter(x=chart_ind.index, y=chart_ind["ENV_LOWER"], name="엔벨로프 하단", line=dict(color="#ec4899", dash="dash")), row=1, col=1)

fig.add_trace(go.Bar(x=chart_ind.index, y=chart_ind["Volume"], name="거래량", marker_color="#94a3b8"), row=2, col=1)

fig.add_trace(go.Scatter(x=chart_ind.index, y=chart_ind["RSI"], name="RSI", line=dict(color="#06b6d4", width=2)), row=3, col=1)
fig.add_hline(y=70, line_color="red", line_dash="dash", row=3, col=1)
fig.add_hline(y=30, line_color="green", line_dash="dash", row=3, col=1)

fig.add_trace(go.Scatter(x=chart_ind.index, y=chart_ind["MACD"], name="MACD", line=dict(color="#3b82f6", width=2)), row=4, col=1)
fig.add_trace(go.Scatter(x=chart_ind.index, y=chart_ind["MACD_SIGNAL"], name="Signal", line=dict(color="#fb7185", width=2)), row=4, col=1)
fig.add_trace(go.Bar(x=chart_ind.index, y=chart_ind["MACD_HIST"], name="Histogram", marker_color="#cbd5e1"), row=4, col=1)

fig.update_layout(
    height=950,
    template="plotly_white",
    xaxis_rangeslider_visible=False,
    legend=dict(orientation="h"),
    margin=dict(l=10, r=10, t=30, b=10)
)

st.plotly_chart(fig, use_container_width=True)

# =========================
# 분석 / 뉴스
# =========================
left, right = st.columns([1.1, 0.9])

with left:
    st.markdown('<div class="sub-card">', unsafe_allow_html=True)
    st.markdown("### 🧠 분석 요약")

    bb_width = latest["BB_UPPER"] - latest["BB_LOWER"]
    bb_pos = ((latest["Close"] - latest["BB_LOWER"]) / bb_width * 100) if bb_width != 0 else np.nan

    a1, a2, a3, a4 = st.columns(4)
    a1.metric("이평 기울기", safe_num(latest["ANGLE"], 2, "°"))
    a2.metric("볼밴 위치", safe_num(bb_pos, 1, "%"))
    a3.metric("엔벨로프 상단", safe_num(latest["ENV_UPPER"]))
    a4.metric("엔벨로프 하단", safe_num(latest["ENV_LOWER"]))

    st.markdown("#### 판단 근거")
    for r in reasons:
        st.write(f"- {r}")

    st.markdown("#### 해석")
    if signal == "강력매수":
        st.success("지표 다수가 긍정 쪽으로 기울어 있어. 분할매수 전략이 상대적으로 안전합니다.")
    elif signal == "매수":
        st.info("흐름은 비교적 양호합니다. 눌림목 확인 후 진입하면 더 안정적일 수 있습니다.")
    elif signal == "관망":
        st.warning("지표가 섞여 있어 확신이 약합니다. 거래량과 MACD 추가 확인이 필요합니다.")
    elif signal == "매도":
        st.error("단기 약세 신호가 우세합니다. 비중 축소나 손절 기준 확인이 필요합니다.")
    else:
        st.error("하락·과열 신호가 겹친 상태입니다. 공격적 진입보다 리스크 관리가 우선입니다.")

    st.markdown('</div>', unsafe_allow_html=True)

with right:
    st.markdown('<div class="sub-card">', unsafe_allow_html=True)
    st.markdown("### 📰 최신 뉴스 / 호재·악재")

    if scored_news:
        for n in scored_news[:6]:
            title_html = n["title"]
            if n["link"]:
                title_html = f'<a href="{n["link"]}" target="_blank" style="text-decoration:none;color:#111827;">{n["title"]}</a>'

            st.markdown(
                f"""
                <div style="padding:12px 10px;border-bottom:1px solid #e5e7eb;">
                    <div style="margin-bottom:6px;">
                        <span class="{n['tag_class']}">{n['tag']}</span>
                    </div>
                    <div style="font-weight:700; line-height:1.5;">{title_html}</div>
                    <div class="small-note">{n['publisher']}</div>
                </div>
                """,
                unsafe_allow_html=True
            )
    else:
        st.info("뉴스 데이터를 가져오지 못했습니다.")

    st.markdown('</div>', unsafe_allow_html=True)

# =========================
# 기업 정보
# =========================
info = fetch_info(yf_symbol)

st.markdown('<div class="sub-card">', unsafe_allow_html=True)
st.markdown("### 🏷️ 기업 기본 정보")
i1, i2, i3, i4 = st.columns(4)
i1.metric("시가총액", safe_num((info.get("marketCap") or 0) / 1e9, 2, "B"))
i2.metric("PER", safe_num(info.get("trailingPE"), 2))
i3.metric("EPS", safe_num(info.get("trailingEps"), 2))
i4.metric("배당수익률", safe_num((info.get("dividendYield") or 0) * 100, 2, "%"))
st.markdown('</div>', unsafe_allow_html=True)

st.markdown("""
<div style="margin-top:18px; text-align:center; font-family:'Inter','Noto Sans KR',sans-serif; color:#64748b; font-size:14px;">
    <a href="mailto:coke_bom@naver.com" style="color:#64748b; text-decoration:none; font-weight:600;">
        coke_bom@naver.com 문의 및 불편사항
    </a>
</div>
""", unsafe_allow_html=True)


st.caption("참고: 이 평가는 규칙 기반 참고 신호이며 실제 투자 손익을 보장하지 않습니다.")
