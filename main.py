import streamlit as st
import yfinance as yf
import pandas as pd
import requests
from bs4 import BeautifulSoup

# --- 設定頁面配置 ---
st.set_page_config(page_title="AI 戰情雷達", layout="wide")

st.title("🚀 AI 戰情雷達 - 自動抓取中文名版")
st.markdown("即時爬取 Yahoo 股市中文名稱，並計算技術指標。")

# --- 側邊欄：輸入觀察清單 ---
st.sidebar.header("📋 觀察清單設定")
default_tickers = "2330, 2317, 3034, 2376, 2383, 2027, 0050, 00878" # 加入了 ETF 測試
user_input = st.sidebar.text_area("輸入股票代號 (用逗號隔開)", default_tickers)

# --- 核心功能：網路爬蟲抓中文名 (含快取機制) ---
@st.cache_data(ttl=86400) # ttl=86400 代表快取存活 24 小時，每天更新一次名稱即可
def get_stock_name_from_web(code):
    """
    爬取 Yahoo 股市 (台灣) 的網頁標題來獲取中文名稱
    """
    try:
        # 1. 設定目標網址 (Yahoo 股市)
        url = f"https://tw.stock.yahoo.com/quote/{code}"
        
        # 2. 發送請求 (假裝是瀏覽器，以免被擋)
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'}
        response = requests.get(url, headers=headers, timeout=5)
        
        # 3. 解析網頁
        if response.status_code == 200:
            soup = BeautifulSoup(response.text, 'html.parser')
            # Yahoo 股市的名稱通常在 <h1 class="C($c-link-text) Fw(b) Fz(24px) My(2px)"> 裡面
            # 但最簡單的方法是抓網頁 Title，通常格式是 "台積電(2330) - 個股走勢..."
            title = soup.title.string
            if title:
                # 切割字串，取出中文部分
                # 格式通常是: "台積電(2330) - 個股走勢..." -> 取 "台積電"
                stock_name = title.split('(')[0].strip()
                return stock_name
    except Exception as e:
        print(f"爬取失敗 {code}: {e}")
    
    # 如果爬失敗，回傳原始代號
    return f"股票 {code}"

# --- 核心函數：計算指標 ---
def calculate_rsi(series, period=14):
    delta = series.diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
    rs = gain / loss
    return 100 - (100 / (1 + rs))

def get_stock_data(tickers):
    data_list = []
    ticker_list = [t.strip() for t in tickers.split(',')]
    
    # 進度條
    progress_text = "正在連線 Yahoo 股市資料庫..."
    my_bar = st.progress(0, text=progress_text)
    
    for i, code in enumerate(ticker_list):
        # 1. 先去網路上抓中文名字 (有快取，速度快)
        name = get_stock_name_from_web(code)
        
        # 2. 抓取股價數據
        symbol = f"{code}.TW"
        stock = yf.Ticker(symbol)
        df = stock.history(period="3mo")
        
        # 嘗試上櫃 (.TWO)
        if len(df) < 5: 
            symbol = f"{code}.TWO"
            stock = yf.Ticker(symbol)
            df = stock.history(period="3mo")
        
        if len(df) > 0:
            # --- 計算指標 ---
            current_price = df['Close'].iloc[-1]
            prev_price = df['Close'].iloc[-2]
            change_pct = ((current_price - prev_price) / prev_price) * 100
            
            # RSI
            rsi_series = calculate_rsi(df['Close'])
            rsi = rsi_series.iloc[-1]
            
            # 量能倍數
            vol_ma5 = df['Volume'].rolling(window=5).mean().iloc[-1]
            current_vol = df['Volume'].iloc[-1]
            vol_ratio = current_vol / vol_ma5 if vol_ma5 > 0 else 0
            
            # 趨勢
            ma20 = df['Close'].rolling(window=20).mean().iloc[-1]
            trend = "🟢 多頭" if current_price > ma20 else "🔴 弱勢"
            
            # --- 訊號邏輯 ---
            signal = "觀察"
            if current_price > ma20 and vol_ratio > 1.2 and 50 < rsi < 70:
                signal = "✨ 買點浮現"
            elif vol_ratio > 1.5 and 60 < rsi < 75:
                signal = "★ 強勢買入"
            elif rsi > 75:
                signal = "⚠️ 過熱警戒"
            elif rsi < 30:
                signal = "🔫 超賣反彈"
            
            data_list.append({
                "代號": code,
                "名稱": name,
                "現價": round(current_price, 1),
                "漲跌%": f"{change_pct:+.2f}%",
                "RSI": round(rsi, 1),
                "量能倍數": round(vol_ratio, 2),
                "趨勢": trend,
                "訊號": signal
            })
            
        # 更新進度條
        my_bar.progress((i + 1) / len(ticker_list), text=f"正在分析: {name} ({code})")
        
    my_bar.empty() # 跑完後隱藏進度條
    return pd.DataFrame(data_list)

# --- 主程式 ---
if user_input:
    result_df = get_stock_data(user_input)
    
    if not result_df.empty:
        # --- 樣式設定 (保持不變) ---
        def highlight_signal(val):
            if '買點' in val or '強勢' in val:
                return 'background-color: #d4edda; color: #155724; font-weight: bold;'
            elif '警戒' in val:
                return 'background-color: #f8d7da; color: #721c24; font-weight: bold;'
            return ''

        def color_trend(val):
            return 'color: green; font-weight: bold;' if '多頭' in val else 'color: red; font-weight: bold;'
            
        def color_change(val):
            return 'color: red;' if '-' in val else 'color: green;'

        st.dataframe(
            result_df.style
            .map(highlight_signal, subset=['訊號'])
            .map(color_trend, subset=['趨勢'])
            .map(color_change, subset=['漲跌%']),
            use_container_width=True,
            height=400
        )
        
        # --- 詳細數據卡片 ---
        st.subheader("🔍 重點個股")
        cols = st.columns(4)
        for index, (i, row) in enumerate(result_df.iterrows()):
            if index < 4:
                with cols[index]:
                    st.metric(
                        label=f"{row['名稱']} ({row['代號']})",
                        value=str(row['現價']),
                        delta=row['漲跌%']
                    )
                    st.write(f"RSI: {row['RSI']} | **{row['訊號']}**")
    else:
        st.warning("查無數據，請確認代號輸入正確。")
else:
    st.info("請在左側輸入股票代號。")
