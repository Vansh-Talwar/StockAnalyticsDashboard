import yfinance as yf                  # For Data
import streamlit as st                 # For sharing interactive web applications
import pandas as pd                    # Data manipulation and analysis
import plotly.graph_objs as go         # For Graphs
import plotly.express as px
from dotenv import load_dotenv         # To Load API
import os
import pytz
from datetime import datetime, timedelta

load_dotenv()

# ── Secret helper ──────────────────────────────────────────
def get_secret(key):
    try:
        value = st.secrets[key]
        if value:
            return value
    except Exception:
        pass
    value = os.getenv(key)
    if value:
        return value
    return None
# ───────────────────────────────────────────────────────────

# Page configuration
st.set_page_config(
    page_title="Stock Analytics Dashboard",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded"
)

st.title("Stock Analytics Dashboard")

# ── Ticker and time range inputs ───────────────────────────
col4, col5 = st.columns(2)
with col4:
    ticker = st.text_input(
        "Enter Stock Ticker (e.g., INFY.NS for Infosys, TCS.NS for TCS, AAPL for Apple)",
        "INFY.NS"
    )
with col5:
    time = st.selectbox(
        "Select time range",
        ['1d', '2d', '5d', '1mo', '3mo', '6mo', '1y', '5y', 'max']
    )

# ── Interval logic ─────────────────────────────────────────
interval_map = {
    '1d': '5m',
    '2d': '5m',
    '5d': '15m',
    '1mo': '1d',
    '3mo': '1d',
    '6mo': '1d',
    '1y': '1d',
    '5y': '1wk',
    'max': '1mo'
}

interval = interval_map[time]

intraday_intervals = ['1m', '2m', '5m', '15m', '30m', '60m', '90m']

if interval in intraday_intervals:
    xaxis_tickformat = '%Y-%m-%d %H:%M'
    time_unit = "minutes"
else:
    xaxis_tickformat = '%Y-%m-%d'
    time_unit = "days"

# ── Fetch price data ───────────────────────────────────────
@st.cache_data(ttl=300)  # cache for 5 minutes
def fetch_stock_data(ticker, start, end, interval):
    return yf.download(ticker, start=start, end=end, interval=interval)

period_to_days = {
    '1d': 1,
    '2d': 2,
    '5d': 5,
    '1mo': 30,
    '3mo': 90,
    '6mo': 180,
    '1y': 365,
    '5y': 1825,
    'max': 7300
}

ist = pytz.timezone("Asia/Kolkata")
end = datetime.now(ist)
start = end - timedelta(days=period_to_days[time])

with st.spinner("Fetching stock data..."):
    df = fetch_stock_data(ticker, start, end, interval)

# ── Empty data check ───────────────────────────────────────
if df.empty:
    if interval in intraday_intervals:
        st.warning("Intraday data unavailable. Markets may be closed or try a different time range.")
    else:
        st.warning("No data found for this ticker or time range. Please check the ticker symbol.")
    st.stop()

# ── Convert index to IST ───────────────────────────────────
if interval in intraday_intervals:
    if df.index.tzinfo is not None:
        df.index = df.index.tz_convert("Asia/Kolkata")
    else:
        df.index = df.index.tz_localize("UTC").tz_convert("Asia/Kolkata")

# ── Flatten MultiIndex columns if needed ───────────────────
if isinstance(df.columns, pd.MultiIndex):
    df.columns = df.columns.get_level_values(0)

# ── Feature engineering ────────────────────────────────────
df["Daily Return"] = df["Close"].pct_change()

if interval == '1d':
    df["SMA20"] = df["Close"].rolling(window=20).mean()
    df["SMA50"] = df["Close"].rolling(window=50).mean()
    df["SMA200"] = df["Close"].rolling(window=200).mean()

# ── RSI calculation ────────────────────────────────────────
def compute_rsi(series, window=14):
    delta = series.diff()
    gain = delta.clip(lower=0).rolling(window).mean()
    loss = -delta.clip(upper=0).rolling(window).mean()
    rs = gain / loss
    rsi = 100 - (100 / (1 + rs))
    return rsi

df["RSI"] = compute_rsi(df["Close"].squeeze())

# ── Volatility calculation ─────────────────────────────────
rolling_window = 20 if interval == '1d' else 14
if interval == '1d':
    # annualized volatility for daily data
    df["Volatility"] = df["Daily Return"].rolling(window=rolling_window).std() * (252 ** 0.5)
else:
    # rolling std of returns for intraday
    df["Volatility"] = df["Daily Return"].rolling(window=rolling_window).std()


# ── Fetch stock info ───────────────────────────────────────
@st.cache_data(ttl=300)
def fetch_stock_info(ticker):
    stock = yf.Ticker(ticker)
    return stock.info

info = fetch_stock_info(ticker)

# ── Company overview ───────────────────────────────────────
st.subheader(info.get('longName', ticker))
col1, col2, col3 = st.columns(3)
with col1:
    st.write("Sector:", info.get('sector', 'N/A'))
    st.write("Current Price:", info.get('currentPrice', 'N/A'))
with col2:
    st.write("Market Cap:", info.get('marketCap', 'N/A'))
    st.write("P/E Ratio:", info.get('trailingPE', 'N/A'))
with col3:
    st.write("52 Week Low:", info.get('fiftyTwoWeekLow', 'N/A'))
    st.write("52 Week High:", info.get('fiftyTwoWeekHigh', 'N/A'))

# ── Candlestick + Volume range input ──────────────────────
label = f"Enter number of {time_unit} for Candlestick + Volume chart"
num_days = st.number_input(label, min_value=1, max_value=len(df), value=min(60, len(df)))

# ── Build charts ───────────────────────────────────────────

# Line chart with SMA
fig = go.Figure()
fig.add_trace(go.Scatter(
    x=df.index,
    y=df['Close'].values.flatten(),
    mode='lines',
    name='Close'
))
if 'SMA20' in df.columns and df['SMA20'].notna().any():
    fig.add_trace(go.Scatter(
        x=df.index,
        y=df['SMA20'].values.flatten(),
        mode='lines',
        name='SMA20',
        line=dict(dash='dashdot')
    ))
if 'SMA50' in df.columns and df['SMA50'].notna().any():
    fig.add_trace(go.Scatter(
        x=df.index,
        y=df['SMA50'].values.flatten(),
        mode='lines',
        name='SMA50',
        line=dict(dash='dot')
    ))
if 'SMA200' in df.columns and df['SMA200'].notna().any():
    fig.add_trace(go.Scatter(
        x=df.index,
        y=df['SMA200'].values.flatten(),
        mode='lines',
        name='SMA200',
        line=dict(dash='dash')
    ))
fig.update_layout(
    title=f"{ticker} Closing Price with SMA 20, 50, 200",
    xaxis_title="Date/Time",
    yaxis_title="Stock Price",
    template="plotly_white",
    plot_bgcolor='black',
    paper_bgcolor='black'
)

# Volume chart
daily_vol = df[['Volume']].tail(num_days)
vol = go.Figure(data=[go.Bar(
    x=daily_vol.index,
    y=daily_vol.values.squeeze(),
    name='Daily Volume',
    marker_color="orange"
)])
vol.update_layout(
    title=f'Daily Volume - Last {num_days} {time_unit} for {ticker}',
    xaxis_title='Date',
    yaxis_title='Volume',
    xaxis_tickformat=xaxis_tickformat,
    template='plotly',
    plot_bgcolor='black',
    paper_bgcolor='black',
    font=dict(color='white')
)

# Candlestick chart
df_candle = df[['Open', 'High', 'Low', 'Close']].dropna().tail(num_days)
candle = go.Figure(data=[go.Candlestick(
    x=df_candle.index,
    open=df_candle['Open'],
    high=df_candle['High'],
    low=df_candle['Low'],
    close=df_candle['Close'],
    increasing_line_color='green',
    decreasing_line_color='red'
)])
candle.update_layout(
    title=f"Candlestick Chart - Last {num_days} {time_unit} for {ticker}",
    xaxis_title='Date',
    yaxis_title='Price',
    xaxis_tickformat=xaxis_tickformat,
    template='plotly_dark',
    plot_bgcolor='black',
    paper_bgcolor='black',
    font=dict(color='white'),
    xaxis_rangeslider_visible=False
)

# RSI chart
rsi_fig = go.Figure()
rsi_fig.add_trace(go.Scatter(
    x=df.index,
    y=df['RSI'].values.flatten(),
    mode='lines',
    name='RSI',
    line=dict(color='cyan')
))
rsi_fig.add_hline(y=70, line_dash='dash', line_color='red',
                  annotation_text='Overbought (70)', annotation_position='bottom right')
rsi_fig.add_hline(y=30, line_dash='dash', line_color='green',
                  annotation_text='Oversold (30)', annotation_position='top right')
rsi_fig.update_layout(
    title=f"{ticker} RSI (14)",
    xaxis_title="Date/Time",
    yaxis_title="RSI",
    yaxis=dict(range=[0, 100]),
    xaxis_tickformat=xaxis_tickformat,
    template='plotly_dark',
    plot_bgcolor='black',
    paper_bgcolor='black',
    font=dict(color='white')
)

# Volatility chart
vol_fig = go.Figure()
vol_fig.add_trace(go.Scatter(
    x=df.index,
    y=df['Volatility'].values.flatten(),
    mode='lines',
    name='Volatility',
    line=dict(color='orange'),
    fill='tozeroy',
    fillcolor='rgba(255,165,0,0.1)'
))
vol_fig.update_layout(
    title=f"{ticker} Rolling Volatility (window={rolling_window})" + (" — Annualized" if interval == '1d' else ""),
    xaxis_title="Date/Time",
    yaxis_title="Volatility",
    xaxis_tickformat=xaxis_tickformat,
    template='plotly_dark',
    plot_bgcolor='black',
    paper_bgcolor='black',
    font=dict(color='white')
)

# Return distribution chart
dist_fig = px.histogram(
    df['Daily Return'].dropna(),
    nbins=50,
    title=f"{ticker} Daily Return Distribution",
    labels={'value': 'Daily Return', 'count': 'Frequency'},
    color_discrete_sequence=['cyan']
)
dist_fig.update_layout(
    template='plotly_dark',
    plot_bgcolor='black',
    paper_bgcolor='black',
    font=dict(color='white'),
    xaxis_title="Daily Return",
    yaxis_title="Frequency"
)

# ── Chart tabs ─────────────────────────────────────────────
tab1, tab2, tab3, tab4 = st.tabs(["Line + SMA", "Volume", "Candlestick", "Indicators"])
with tab1:
    st.subheader("Closing Price Line Chart")
    st.plotly_chart(fig, use_container_width=True)
with tab2:
    st.subheader("Daily Volume Chart")
    st.plotly_chart(vol, use_container_width=True)
with tab3:
    st.subheader("Candlestick Chart")
    st.plotly_chart(candle, use_container_width=True)
with tab4:
    st.subheader("RSI — Relative Strength Index (14)")
    st.caption("RSI above 70 = overbought. RSI below 30 = oversold.")
    st.plotly_chart(rsi_fig, use_container_width=True)

    st.subheader("Rolling Volatility")
    st.caption("Higher volatility means larger price swings. Annualized for daily data.")
    st.plotly_chart(vol_fig, use_container_width=True)

    st.subheader("Daily Return Distribution")
    st.caption("Shows how returns are spread. A normal bell curve suggests random walk behaviour.")
    st.plotly_chart(dist_fig, use_container_width=True)

# ── Expanders — raw data and financials ────────────────────
with st.expander("Show Raw Stock Data"):
    st.subheader("Stock Data")
    st.write(df)

with st.expander("Show Financials"):
    st.subheader("Income Statement")
    st.write(stock.financials)
    st.subheader("Balance Sheet")
    st.write(stock.balance_sheet)
    st.subheader("Cash Flow")
    st.write(stock.cash_flow)

# ── News section ───────────────────────────────────────────
if st.button("Get News"):
    news_api_key = get_secret("NEWS_API_KEY")
    if not news_api_key:
        st.error("NEWS_API_KEY missing. Add it to .env locally or Streamlit Secrets on Cloud.")
        st.stop()

    raw_name = info.get('longName', ticker)
    clean_name = (
        raw_name
        .replace(' Limited', '')
        .replace(' Ltd.', '')
        .replace(' Inc.', '')
        .replace(' Corp.', '')
        .replace(' Corporation', '')
        .strip()
    )
    # Strip exchange suffix for ticker symbol
    clean_ticker = ticker.replace('.NS', '').replace('.BO', '').replace('.BSE', '')
    search_query = clean_name

    with st.spinner(f"Fetching news for {clean_name}..."):
        try:
            import requests
            url = "https://newsapi.org/v2/everything"
            params = {
                "q": search_query,
                "language": "en",
                "sortBy": "relevancy",
                "pageSize": 10,
                "apiKey": news_api_key
            }
            response = requests.get(url, params=params, timeout=10)
            news = response.json()

            if news['status'] == 'ok' and news['totalResults'] > 0:
                for article in news['articles']:
                    st.subheader(article['title'])
                    st.write(f"Source: {article['source']['name']}")
                    st.write(f"Published at: {article['publishedAt']}")
                    st.write(article.get('description') or "")
                    st.markdown(f"[Read more...]({article['url']})")
                    st.markdown("---")
            else:
                st.warning(f"No news found. API message: {news.get('message', 'No message')}")
        except requests.exceptions.Timeout:
            st.error("News request timed out. Try again.")
        except Exception as e:
            st.error(f"Error fetching news: {e}")