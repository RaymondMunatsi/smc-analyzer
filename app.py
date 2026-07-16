import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import plotly.graph_objects as go

# Set Page Config (Optimized for Mobile)
st.set_page_config(page_title="SMC Mobile Analyzer", layout="centered")

st.title("📊 SMC Mobile Analyzer")
st.caption("Automated Order Blocks, Liquidity Sweeps, & Market Structure")

# --- Sidebar Controls (Tucks neatly into mobile menu) ---
st.sidebar.header("Asset & Timeframe")
ticker_input = st.sidebar.selectbox(
    "Select Asset",
    ["EURUSD=X", "GBPUSD=X", "USDJPY=X", "^SPX", "^IXIC", "^DJI"],
    index=0
)
period = st.sidebar.selectbox("History Period", ["5d", "1mo", "3mo", "6mo"], index=1)
interval = st.sidebar.selectbox("Timeframe", ["15m", "30m", "1h", "4h", "1d"], index=2)

# Parameters
st.sidebar.header("SMC Settings")
swing_window = st.sidebar.slider("Swing High/Low Lookback", 3, 15, 5)
ob_pullback_pct = st.sidebar.slider("OB Strong Expansion Threshold (%)", 0.05, 1.0, 0.15, step=0.05)

# --- Data Fetching ---
@st.cache_data(ttl=60)
def fetch_data(ticker, period, interval):
    data = yf.download(ticker, period=period, interval=interval)
    if isinstance(data.columns, pd.MultiIndex):
        data.columns = [col[0] for col in data.columns]
    data.reset_index(inplace=True)
    data.rename(columns={"Datetime": "timestamp", "Date": "timestamp"}, inplace=True)
    return data

df = fetch_data(ticker_input, period, interval)

if df.empty:
    st.error("Failed to fetch data.")
    st.stop()

# --- SMC Calculation Engine ---
def calculate_smc(df, swing_window, ob_threshold):
    df = df.copy()
    n = len(df)
    
    # 1. Detect Swing Highs & Lows
    df['swing_high'] = np.nan
    df['swing_low'] = np.nan
    
    for i in range(swing_window, n - swing_window):
        window_highs = df['High'].iloc[i - swing_window: i + swing_window + 1]
        if df['High'].iloc[i] == window_highs.max():
            df.loc[i, 'swing_high'] = df['High'].iloc[i]
            
        window_lows = df['Low'].iloc[i - swing_window: i + swing_window + 1]
        if df['Low'].iloc[i] == window_lows.min():
            df.loc[i, 'swing_low'] = df['Low'].iloc[i]

    # Forward fill last swings
    df['last_high'] = df['swing_high'].ffill()
    df['last_low'] = df['swing_low'].ffill()

    # 2. Detect Liquidity Sweeps
    df['liquidity_sweep'] = "None"
    for i in range(1, n):
        prev_high = df['last_high'].iloc[i-1]
        prev_low = df['last_low'].iloc[i-1]
        
        if pd.notna(prev_high) and df['High'].iloc[i] > prev_high and df['Close'].iloc[i] < prev_high:
            df.loc[i, 'liquidity_sweep'] = "Buyside Sweep (Bearish reversal hint)"
        elif pd.notna(prev_low) and df['Low'].iloc[i] < prev_low and df['Close'].iloc[i] > prev_low:
            df.loc[i, 'liquidity_sweep'] = "Sellside Sweep (Bullish reversal hint)"

    # 3. Detect Order Blocks
    df['order_block'] = "None"
    df['ob_price'] = np.nan
    
    for i in range(1, n - 2):
        move_up = (df['Close'].iloc[i+2] - df['Open'].iloc[i+1]) / df['Open'].iloc[i+1] * 100
        move_down = (df['Open'].iloc[i+1] - df['Close'].iloc[i+2]) / df['Open'].iloc[i+1] * 100
        
        # Bullish OB (Demand)
        if move_up > ob_threshold and df['Close'].iloc[i] < df['Open'].iloc[i]:
            df.loc[i, 'order_block'] = "Bullish OB (Demand Zone)"
            df.loc[i, 'ob_price'] = df['Low'].iloc[i]
            
        # Bearish OB (Supply)
        elif move_down > ob_threshold and df['Close'].iloc[i] > df['Open'].iloc[i]:
            df.loc[i, 'order_block'] = "Bearish OB (Supply Zone)"
            df.loc[i, 'ob_price'] = df['High'].iloc[i]
            
    return df

processed_df = calculate_smc(df, swing_window, ob_pullback_pct)

# --- 🚨 Mobile Optimized Live Signals ---
st.subheader("🚨 Live Mobile Signals")

with st.container():
    st.markdown("### 🏦 Institutional Activity")
    recent_obs = processed_df[processed_df['order_block'] != "None"].tail(3)
    if not recent_obs.empty:
        for idx, row in recent_obs.iterrows():
            color = "🟢" if "Bullish" in row['order_block'] else "🔴"
            st.info(f"{color} **{row['order_block']}** zone established at **{row['ob_price']:.5f}**")
    else:
        st.write("No fresh Order Blocks in the current view.")

st.markdown("---")

with st.container():
    st.markdown("### 🏹 Liquidity Scrape Alerts")
    recent_sweeps = processed_df[processed_df['liquidity_sweep'] != "None"].tail(1)
    if not recent_sweeps.empty:
        st.warning(f"⚠️ **{recent_sweeps.iloc[0]['liquidity_sweep']}**")
    else:
        st.success("✅ Price action is stable. No active liquidity traps.")

st.markdown("---")

# --- Interactive Plotly Chart (Touch Friendly) ---
st.subheader("📈 Interactive Chart")
fig = go.Figure(data=[go.Candlestick(
    x=processed_df['timestamp'],
    open=processed_df['Open'],
    high=processed_df['High'],
    low=processed_df['Low'],
    close=processed_df['Close'],
    name="Price"
)])

# Add Swing Highs
sh_df = processed_df[processed_df['swing_high'].notna()]
fig.add_trace(go.Scatter(
    x=sh_df['timestamp'], y=sh_df['swing_high'],
    mode='markers', marker=dict(color='red', size=8, symbol='triangle-down'),
    name='Swing High'
))

# Add Swing Lows
sl_df = processed_df[processed_df['swing_low'].notna()]
fig.add_trace(go.Scatter(
    x=sl_df['timestamp'], y=sl_df['swing_low'],
    mode='markers', marker=dict(color='green', size=8, symbol='triangle-up'),
    name='Swing Low'
))

# Highlight Order Blocks
bull_ob = processed_df[processed_df['order_block'] == "Bullish OB (Demand Zone)"]
fig.add_trace(go.Scatter(
    x=bull_ob['timestamp'], y=bull_ob['ob_price'],
    mode='markers', marker=dict(color='blue', size=10, symbol='square'),
    name='Bullish OB (Buy Area)'
))

bear_ob = processed_df[processed_df['order_block'] == "Bearish OB (Supply Zone)"]
fig.add_trace(go.Scatter(
    x=bear_ob['timestamp'], y=bear_ob['ob_price'],
    mode='markers', marker=dict(color='orange', size=10, symbol='square'),
    name='Bearish OB (Sell Area)'
))

fig.update_layout(
    xaxis_rangeslider_visible=False,
    height=500, # Height optimized for vertical mobile screens
    template="plotly_dark",
    margin=dict(l=10, r=10, t=30, b=10), # Tight margins for small screens
    legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
)
st.plotly_chart(fig, use_container_width=True)
