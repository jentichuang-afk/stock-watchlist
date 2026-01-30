import streamlit as st
import yfinance as yf
import pandas as pd
import requests
from bs4 import BeautifulSoup
import google.generativeai as genai

# --- 設定頁面配置 ---
st.set_page_config(page_title="AI 戰情雷達 (2026 Live)", layout="wide")

st.title("🚀 AI 戰情雷達 - 2026 智能版")
st.markdown("自動鎖定 Google 最新的 Gemini 模型 (2.0/3.0)，即時掃描台股戰情。")

# --- 側邊欄：設定 ---
st.sidebar.header("⚙️ 核心設定")

# 1. 模型選擇 (升級：加入自動更新別名)
st.sidebar.subheader("🧠 AI 模型引擎")

# 2026 年的主流模型清單
model_map = {
    "🚀 自動最新極速版 (gemini-flash-latest)": "gemini-flash-latest", # 永遠指向最新的 Flash (如 2.0 Flash)
    "🧠 自動最新深度版 (gemini-pro-latest)": "gemini-pro-latest",     # 永遠指向最新的 Pro (如 2.0 Pro)
    "⚡ Gemini 2.0 Flash (指定版本)": "gemini-2.0-flash",            # 鎖定特定版本
    "💎 Gemini 2.0 Pro (指定版本)": "gemini-2.0-pro",                # 鎖定特定版本
    "🧪 實驗性模型 (Experimental)": "gemini-2.0-flash-exp"           # 嚐鮮版
}

selected_label = st.sidebar.selectbox(
    "選擇分析大腦",
    list(model_map.keys()),
    index=0, # 預設選第一個「自動最新版」，這樣您永遠不用改扣
    help="選擇 'latest' 系列，Google 會自動幫您升級到當下最強模型。"
)
model_name = model_map[selected_label]

# 2. 觀察清單
st.sidebar.subheader("📋 觀察清單")
default_tickers = "2330, 2317, 3034, 2376, 2383, 2027, 0050"
user_input = st.sidebar.text_area("輸入股票代號 (用逗號隔開)", default_tickers)

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
    """
    使用 Google Gemini API 分析 (支援 latest 別名)
    """
    # 1. 設定 API Key
    if "GEMINI_API_KEY" in st.secrets:
        # 配合您的截圖，這裡使用 GEMINI_API_KEY 這個變數名稱
        genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
    elif "GOOGLE_API_KEY" in st.secrets:
        # 相容舊設定
        genai.configure(api_key=st.secrets["GOOGLE_API_KEY"])
    else:
        return "❌ 錯誤：找不到 API Key，請檢查 secrets.toml"

    # 2. 準備數據與 Prompt
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
    
    # 3. 呼叫模型
    try:
        # 這裡會直接使用使用者選到的 (例如 gemini-flash-latest)
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
    ticker_list = [t.strip() for t in tickers.split(',')]
    
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
        
        st.dataframe(result_df.style.map(highlight_signal, subset=['訊號']), use_container_width=True, height=400)
        
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
