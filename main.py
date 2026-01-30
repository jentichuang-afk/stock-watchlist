import streamlit as st
import yfinance as yf
import pandas as pd
import requests
from bs4 import BeautifulSoup
import google.generativeai as genai
import os # <--- 新增：用來處理檔案讀寫

# --- 設定頁面配置 ---
st.set_page_config(page_title="AI 戰情雷達 (記憶版)", layout="wide")

st.title("🚀 AI 戰情雷達 - 2026 智能記憶版")
st.markdown("自動記憶您的觀察清單，並鎖定 Google 最新 Gemini 模型進行分析。")

# --- 核心設定：檔案存取 (新增功能) ---
WATCHLIST_FILE = 'watchlist.txt' # 儲存清單的檔案名稱

def load_watchlist():
    """從檔案讀取清單，如果檔案不存在則回傳預設值"""
    default_tickers = "2330, 2317, 3034, 2376, 2383, 2027, 0050"
    if os.path.exists(WATCHLIST_FILE):
        try:
            with open(WATCHLIST_FILE, 'r', encoding='utf-8') as f:
                content = f.read().strip()
                if content: # 確保不是空檔案
                    return content
        except:
            pass # 讀取失敗就用預設值
    return default_tickers

def save_watchlist(tickers):
    """將清單存入檔案"""
    try:
        with open(WATCHLIST_FILE, 'w', encoding='utf-8') as f:
            f.write(tickers)
    except Exception as e:
        st.error(f"存檔失敗: {e}")

# --- 側邊欄：設定 ---
st.sidebar.header("⚙️ 核心設定")

# 1. 模型選擇
st.sidebar.subheader("🧠 AI 模型引擎")
model_map = {
    "🚀 自動最新極速版 (gemini-flash-latest)": "gemini-flash-latest",
    "🧠 自動最新深度版 (gemini-pro-latest)": "gemini-pro-latest",
    "⚡ Gemini 2.0 Flash (指定版本)": "gemini-2.0-flash",
    "💎 Gemini 2.0 Pro (指定版本)": "gemini-2.0-pro",
    "🧪 實驗性模型 (Experimental)": "gemini-2.0-flash-exp"
}
selected_label = st.sidebar.selectbox(
    "選擇分析大腦",
    list(model_map.keys()),
    index=0,
    help="選擇 'latest' 系列，Google 會自動幫您升級到當下最強模型。"
)
model_name = model_map[selected_label]

# 2. 觀察清單 (升級：自動讀取與儲存)
st.sidebar.subheader("📋 觀察清單 (自動儲存)")

# 步驟 A: 先讀取舊紀錄
saved_tickers = load_watchlist()

# 步驟 B: 顯示在輸入框 (預設值設為讀取到的內容)
user_input = st.sidebar.text_area(
    "輸入股票代號 (用逗號隔開)", 
    value=saved_tickers,
    height=150
)

# 步驟 C: 檢查是否變更，若變更則立即存檔
if user_input != saved_tickers:
    save_watchlist(user_input)
    # 不需顯示成功訊息，以免干擾畫面，默默存檔即可

# --- 核心功能：網路爬蟲抓中文名 ---
@st.cache_data(ttl=86400)
def get_stock_name_from_web(code):
    try:
        url = f"https://tw.stock.yahoo.com/quote/{code}"
        headers = {'User-Agent': 'Mozilla/5.0'}
        response = requests.get(url, headers=headers, timeout=3)
        if response.status_code == 200:
            soup = BeautifulSoup(response.text, 'html.parser')
            title = soup.title.string
            if title:
                return title.split('(')[0].strip()
    except:
        pass
    return f"股票 {code}"

# --- 核心功能：Gemini AI 分析 ---
def get_gemini_analysis(df, model_id):
    if "GEMINI_API_KEY" in st.secrets:
        genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
    elif "GOOGLE_API_KEY" in st.secrets:
        genai.configure(api_key=st.secrets["GOOGLE_API_KEY"])
    else:
        return "❌ 錯誤：找不到 API Key，請檢查 secrets.toml"

    data_text = df.to_string(index=False)
    
    prompt = f"""
    現在時間是 2026 年，你是一位使用最先進 AI 輔助的王牌操盤手。
    請根據以下即時盤中數據，為我進行戰情分析。
    
    【數據清單】：
    {data_text}
    
    【分析要求】：
    1. 🎯 **鷹眼點將**：直接點名結構最強（量價齊揚）與最弱（誘多/破線）的個股。
    2. ⚖️ **多空判斷**：針對出現「買點浮現」訊號的股票，判斷是真突破還是假動作？
    3. 💡 **操作指引**：給出明確建議（追價/觀望/停損），不要模稜兩可。
    4. 使用繁體中文，語氣專業、簡潔，善用 Emoji。
    """
    
    try:
        model = genai.GenerativeModel(model_id)
        response = model.generate_content(prompt)
        return response.text
    except Exception as e:
        return f"⚠️ AI 分析發生錯誤 (Model: {model_id}): {e}\n如果是 'latest' 模型報錯，代表該別名暫時無法使用，請切換回指定版本。"

# --- 核心函數：計算指標 ---
def calculate_rsi(series, period=14):
    delta = series.diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
    rs = gain / loss
    return 100 - (100 / (1 + rs))

def get_stock_data(tickers):
    data_list = []
    # 處理全形逗號與空格
    clean_tickers = tickers.replace("，", ",").split(',')
    ticker_list = [t.strip() for t in clean_tickers if t.strip()]
    
    progress_text = "連線 Yahoo 股市資料庫..."
    my_bar = st.progress(0, text=progress_text)
    
    for i, code in enumerate(ticker_list):
        name = get_stock_name_from_web(code)
        
        symbol = f"{code}.TW"
        stock = yf.Ticker(symbol)
        df = stock.history(period="3mo")
        
        if len(df) < 5: 
            symbol = f"{code}.TWO"
            stock = yf.Ticker(symbol)
            df = stock.history(period="3mo")
        
        if len(df) > 0:
            current_price = df['Close'].iloc[-1]
            ma20 = df['Close'].rolling(window=20).mean().iloc[-1]
            vol_ma5 = df['Volume'].rolling(window=5).mean().iloc[-1]
            current_vol = df['Volume'].iloc[-1]
            rsi = calculate_rsi(df['Close']).iloc[-1]
            
            # 簡易漲跌幅
            change_pct = ((current_price - df['Close'].iloc[-2]) / df['Close'].iloc[-2]) * 100
            vol_ratio = current_vol / vol_ma5 if vol_ma5 > 0 else 0
            trend = "🟢 多頭" if current_price > ma20 else "🔴 弱勢"
            
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
                "代號": code, "名稱": name, "現價": round(current_price, 1),
                "漲跌%": f"{change_pct:+.2f}%", "RSI": round(rsi, 1),
                "量能倍數": round(vol_ratio, 2), "趨勢": trend, "訊號": signal
            })
            
        my_bar.progress((i + 1) / len(ticker_list), text=f"正在分析: {name} ({code})")
        
    my_bar.empty()
    return pd.DataFrame(data_list)

# --- 主程式 ---
if user_input:
    result_df = get_stock_data(user_input)
    
    if not result_df.empty:
        # --- 樣式設定 ---
        def highlight_signal(val):
            if '買點' in val or '強勢' in val: return 'background-color: #d4edda; color: #155724; font-weight: bold;'
            elif '警戒' in val: return 'background-color: #f8d7da; color: #721c24; font-weight: bold;'
            return ''
        
        def color_change(val):
            return 'color: red;' if '-' in val else 'color: green;'

        st.dataframe(
            result_df.style
            .map(highlight_signal, subset=['訊號'])
            .map(color_change, subset=['漲跌%']), 
            use_container_width=True, 
            height=400
        )
        
        # --- Gemini AI 分析區塊 ---
        st.divider()
        st.subheader(f"🤖 Gemini 戰情室")
        st.caption(f"目前使用引擎: `{model_name}` (2026 最新版)")
        
        if st.button("呼叫 AI 操盤手分析"):
            with st.spinner(f'正在連線 Google 2026 運算中心...'):
                analysis_result = get_gemini_analysis(result_df, model_name)
                st.markdown(analysis_result)
    else:
        st.warning("查無數據。")
else:
    st.info("請輸入股票代號。")
