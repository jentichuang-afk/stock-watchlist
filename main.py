import streamlit as st
import yfinance as yf
import pandas as pd
import requests
from bs4 import BeautifulSoup
import google.generativeai as genai
import os

# --- 設定頁面配置 ---
st.set_page_config(page_title="AI 戰情雷達 (Pro)", layout="wide")

st.title("🚀 AI 戰情雷達 - 全方位指標版")
st.markdown("整合 MACD、KD、RSI 與量能分析，打造 F1 等級的操盤儀表板。")

# --- 核心設定：檔案存取 ---
WATCHLIST_FILE = 'watchlist.txt'

def load_watchlist():
    default_tickers = "2330, 2317, 3034, 2376, 2383, 2027, 0050"
    if os.path.exists(WATCHLIST_FILE):
        try:
            with open(WATCHLIST_FILE, 'r', encoding='utf-8') as f:
                content = f.read().strip()
                if content: return content
        except: pass
    return default_tickers

def save_watchlist(tickers):
    try:
        with open(WATCHLIST_FILE, 'w', encoding='utf-8') as f:
            f.write(tickers)
    except: pass

# --- 側邊欄設定 ---
st.sidebar.header("⚙️ 核心設定")

# 1. 模型選擇
st.sidebar.subheader("🧠 AI 模型引擎")
model_map = {
    "🚀 自動最新極速版 (gemini-flash-latest)": "gemini-flash-latest",
    "🧠 自動最新深度版 (gemini-pro-latest)": "gemini-pro-latest",
    "⚡ Gemini 2.0 Flash": "gemini-2.0-flash",
    "💎 Gemini 2.0 Pro": "gemini-2.0-pro"
}
selected_label = st.sidebar.selectbox("選擇分析大腦", list(model_map.keys()), index=0)
model_name = model_map[selected_label]

# 2. 觀察清單

# --- 新增這兩行：顯示檔案路徑 ---
current_path = os.path.abspath(WATCHLIST_FILE)
st.sidebar.caption(f"📁 清單檔案位置：\n{current_path}")
# -----------------------------
st.sidebar.subheader("📋 觀察清單")
saved_tickers = load_watchlist()
user_input = st.sidebar.text_area("輸入代號", value=saved_tickers, height=150)
if user_input != saved_tickers: save_watchlist(user_input)

# --- 爬蟲抓中文名 ---
@st.cache_data(ttl=86400)
def get_stock_name_from_web(code):
    try:
        url = f"https://tw.stock.yahoo.com/quote/{code}"
        headers = {'User-Agent': 'Mozilla/5.0'}
        response = requests.get(url, headers=headers, timeout=3)
        if response.status_code == 200:
            soup = BeautifulSoup(response.text, 'html.parser')
            title = soup.title.string
            if title: return title.split('(')[0].strip()
    except: pass
    return f"{code}"

# --- 🔥 技術指標計算核心 (升級重點) ---

def calculate_technical_indicators(df):
    # 1. RSI (14)
    delta = df['Close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
    rs = gain / loss
    df['RSI'] = 100 - (100 / (1 + rs))

    # 2. MACD (12, 26, 9)
    exp1 = df['Close'].ewm(span=12, adjust=False).mean()
    exp2 = df['Close'].ewm(span=26, adjust=False).mean()
    df['MACD'] = exp1 - exp2
    df['Signal_Line'] = df['MACD'].ewm(span=9, adjust=False).mean()
    # MACD 柱狀體 (用於判斷動能強弱)
    df['MACD_Hist'] = df['MACD'] - df['Signal_Line']

    # 3. KD (9, 3, 3) - 台股參數通常用 9
    low_min = df['Low'].rolling(window=9).min()
    high_max = df['High'].rolling(window=9).max()
    df['RSV'] = (df['Close'] - low_min) / (high_max - low_min) * 100
    # 遞迴計算 K 與 D (需處理 NaN)
    k_values = [50] # 初始值
    d_values = [50]
    for i in range(1, len(df)):
        rsv = df['RSV'].iloc[i]
        if pd.isna(rsv):
            k_values.append(k_values[-1])
            d_values.append(d_values[-1])
        else:
            k = (1/3) * rsv + (2/3) * k_values[-1]
            d = (1/3) * k + (2/3) * d_values[-1]
            k_values.append(k)
            d_values.append(d)
    
    df['K'] = k_values
    df['D'] = d_values
    
    return df

# --- Gemini AI 分析 ---
def get_gemini_analysis(df, model_id):
    if "GEMINI_API_KEY" in st.secrets:
        genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
    elif "GOOGLE_API_KEY" in st.secrets:
        genai.configure(api_key=st.secrets["GOOGLE_API_KEY"])
    else:
        return "❌ 錯誤：找不到 API Key"

    data_text = df.to_string(index=False)
    
    # 升級版 Prompt：教 AI 看 MACD 和 KD
    prompt = f"""
    現在是 2026 年，請擔任王牌操盤手。根據以下數據（含 RSI, MACD, KD, 量能）進行分析。
    
    【數據清單】：
    {data_text}
    
    【指標說明】：
    * MACD_Hist > 0 代表多頭動能，數值變大代表加速。
    * K > D (黃金交叉) 為買進訊號；K > 80 為高檔區。
    
    【分析要求】：
    1. 🏆 **冠軍像**：點名目前「三線合一」（RSI強、MACD紅柱、KD金叉）的最強股。
    2. ⚠️ **未爆彈**：找出「指標背離」的股票（例如股價創高但 MACD 轉弱）。
    3. 🎯 **操作建議**：針對每檔股票給出簡短評級（強力買進 / 拉回買進 / 觀望 / 賣出）。
    4. 使用繁體中文，專業且犀利。
    """
    
    try:
        model = genai.GenerativeModel(model_id)
        response = model.generate_content(prompt)
        return response.text
    except Exception as e:
        return f"AI 錯誤: {e}"

# --- 抓取數據主程式 ---
def get_stock_data(tickers):
    data_list = []
    clean_tickers = tickers.replace("，", ",").split(',')
    ticker_list = [t.strip() for t in clean_tickers if t.strip()]
    
    my_bar = st.progress(0, text="連線 Yahoo 股市...")
    
    for i, code in enumerate(ticker_list):
        name = get_stock_name_from_web(code)
        symbol = f"{code}.TW"
        stock = yf.Ticker(symbol)
        df = stock.history(period="6mo") # 抓長一點的時間以計算 MACD
        
        if len(df) < 20: 
            symbol = f"{code}.TWO"
            stock = yf.Ticker(symbol)
            df = stock.history(period="6mo")
        
        if len(df) > 30:
            # 計算所有指標
            df = calculate_technical_indicators(df)
            
            # 取最新一筆資料
            last = df.iloc[-1]
            prev = df.iloc[-2]
            
            # 整理顯示數據
            price = last['Close']
            change_pct = ((price - prev['Close']) / prev['Close']) * 100
            
            # 訊號判斷
            vol_ratio = last['Volume'] / df['Volume'].rolling(5).mean().iloc[-1] if df['Volume'].rolling(5).mean().iloc[-1] > 0 else 0
            
            macd_signal = "🟢 偏多" if last['MACD_Hist'] > 0 else "🔴 偏空"
            kd_signal = "✨ 金叉" if last['K'] > last['D'] and prev['K'] < prev['D'] else ("💀 死叉" if last['K'] < last['D'] and prev['K'] > prev['D'] else "")
            
            # 綜合訊號
            final_signal = "觀察"
            if last['MACD_Hist'] > 0 and last['K'] > last['D'] and vol_ratio > 1.0:
                final_signal = "★ 強勢進攻"
            elif last['RSI'] < 30 and last['K'] < 20:
                final_signal = "🔫 超跌反彈"
            
            data_list.append({
                "代號": code, "名稱": name, 
                "現價": round(price, 1),
                "漲跌%": f"{change_pct:+.2f}%",
                "量能": f"{round(vol_ratio, 1)}x",
                "RSI": round(last['RSI'], 1),
                "KD值": f"K{int(last['K'])}/D{int(last['D'])}",
                "MACD": macd_signal,
                "狀態": final_signal + f" {kd_signal}"
            })
            
        my_bar.progress((i + 1) / len(ticker_list), text=f"正在分析: {name}")
        
    my_bar.empty()
    return pd.DataFrame(data_list)

# --- 主畫面 ---
if user_input:
    result_df = get_stock_data(user_input)
    
    if not result_df.empty:
        # 樣式表
        def highlight_signal(val):
            if '強勢' in val: return 'background-color: #d4edda; color: #155724; font-weight: bold;'
            if '死叉' in val or '偏空' in val: return 'color: #dc3545;'
            return ''
        
        st.dataframe(
            result_df.style
            .map(highlight_signal, subset=['狀態', 'MACD'])
            .map(lambda x: 'color: red' if '-' in x else 'color: green', subset=['漲跌%']),
            use_container_width=True, height=400
        )
        
        st.divider()
        st.subheader("🤖 Gemini 戰情室")
        if st.button("呼叫 AI 操盤手 (包含 MACD/KD 分析)"):
            with st.spinner(f'AI 正在交叉比對 RSI 與 MACD 數據...'):
                analysis_result = get_gemini_analysis(result_df, model_name)
                st.markdown(analysis_result)
    else:
        st.warning("查無數據。")
else:
    st.info("請輸入代號。")

