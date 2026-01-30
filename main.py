import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np

# --- 設定頁面配置 ---
st.set_page_config(page_title="AI 戰情雷達", layout="wide")

st.title("🚀 AI 戰情雷達 - 自選股監控")
st.markdown("輸入台股代號（用逗號隔開），系統將自動計算 RSI、量能倍數並給出訊號。")

# --- 側邊欄：輸入觀察清單 ---
st.sidebar.header("📋 觀察清單設定")
default_tickers = "2330, 2376, 3034, 2317, 2383, 2027"
user_input = st.sidebar.text_area("輸入股票代號 (例如: 2330, 2376)", default_tickers)

# --- 核心函數：計算指標 ---
def calculate_rsi(series, period=14):
    delta = series.diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
    rs = gain / loss
    return 100 - (100 / (1 + rs))

def get_stock_data(tickers):
    data_list = []
    
    # 處理輸入字串，轉為 List
    ticker_list = [t.strip() for t in tickers.split(',')]
    
    progress_bar = st.progress(0)
    
    for i, code in enumerate(ticker_list):
        # 台股代號需加上 .TW (上市) 或 .TWO (上櫃)
        # 這裡預設先嘗試 .TW，實際應用可更細緻處理
        symbol = f"{code}.TW"
        stock = yf.Ticker(symbol)
        
        # 抓取歷史資料 (抓 2 個月以計算 MA 和 RSI)
        df = stock.history(period="3mo")
        
        if len(df) < 20: # 若抓不到資料或資料過少 (可能是上櫃股，試試 .TWO)
            symbol = f"{code}.TWO"
            stock = yf.Ticker(symbol)
            df = stock.history(period="3mo")
        
        if len(df) > 0:
            # 取得基本資訊
            try:
                info = stock.info
                name = info.get('longName', code) # 簡化名稱獲取
                # 簡化中文名稱處理 (yfinance 有時中文名稱會顯示亂碼或英文，這裡做個備用顯示)
                if not name or name == code:
                    name = f"股票 {code}"
            except:
                name = code

            # --- 計算指標 ---
            current_price = df['Close'].iloc[-1]
            prev_price = df['Close'].iloc[-2]
            change_pct = ((current_price - prev_price) / prev_price) * 100
            
            # RSI 計算
            rsi_series = calculate_rsi(df['Close'])
            rsi = rsi_series.iloc[-1]
            
            # 量能倍數 (今日成交量 / 過去 5 日均量)
            vol_ma5 = df['Volume'].rolling(window=5).mean().iloc[-1]
            current_vol = df['Volume'].iloc[-1]
            vol_ratio = current_vol / vol_ma5 if vol_ma5 > 0 else 0
            
            # 趨勢判定 (價格在 20MA 之上為多頭)
            ma20 = df['Close'].rolling(window=20).mean().iloc[-1]
            trend = "🟢 多頭" if current_price > ma20 else "🔴 弱勢"
            
            # --- 訊號邏輯 (模仿您的分析風格) ---
            signal = "觀察"
            
            # 買點邏輯：趨勢多頭 + 量能放大 + RSI 健康(沒過熱)
            if current_price > ma20 and vol_ratio > 1.2 and 50 < rsi < 70:
                signal = "✨ 買點浮現"
            # 強勢買入：量能爆發 + RSI 強勢
            elif vol_ratio > 1.5 and 60 < rsi < 75:
                signal = "★ 強勢買入"
            # 過熱警示
            elif rsi > 75:
                signal = "⚠️ 過熱警戒"
            # 抄底邏輯 (乖離過大)
            elif rsi < 30:
                signal = "🔫 超賣反彈"
            
            data_list.append({
                "代號": code,
                "名稱": name, # yfinance 中文支援度不一，實務上通常需自建代號對照表
                "現價": round(current_price, 1),
                "漲跌%": f"{change_pct:+.2f}%",
                "RSI": round(rsi, 1),
                "量能倍數": round(vol_ratio, 2),
                "趨勢": trend,
                "訊號": signal
            })
            
        progress_bar.progress((i + 1) / len(ticker_list))
        
    return pd.DataFrame(data_list)

# --- 主程式邏輯 ---
if user_input:
    with st.spinner('正在掃描市場數據...'):
        result_df = get_stock_data(user_input)
    
    if not result_df.empty:
        # --- 樣式美化 ---
        # 定義顏色函式
        def highlight_signal(val):
            color = ''
            if '買點' in val or '強勢' in val:
                color = 'background-color: #d4edda; color: #155724; font-weight: bold;' # 綠底深綠字
            elif '警戒' in val:
                color = 'background-color: #f8d7da; color: #721c24; font-weight: bold;' # 紅底深紅字
            return color

        def color_trend(val):
            color = 'color: green;' if '多頭' in val else 'color: red;'
            return color
            
        def color_change(val):
            return 'color: red;' if '-' in val else 'color: green;'

        # 顯示互動式表格
        st.dataframe(
            result_df.style
            .map(highlight_signal, subset=['訊號'])
            .map(color_trend, subset=['趨勢'])
            .map(color_change, subset=['漲跌%']),
            use_container_width=True,
            height=400
        )
        
        # --- 詳細數據卡片區 ---
        st.subheader("🔍 重點個股詳細數據")
        cols = st.columns(len(result_df))
        for index, (i, row) in enumerate(result_df.iterrows()):
            # 只顯示前 4 檔以免版面太擠
            if index < 4:
                with cols[index]:
                    st.metric(
                        label=f"{row['代號']} {row['趨勢'].split(' ')[1]}",
                        value=str(row['現價']),
                        delta=row['漲跌%']
                    )
                    st.caption(f"RSI: {row['RSI']} | 量能: {row['量能倍數']}x")
                    st.write(f"**{row['訊號']}**")

        st.info("💡 提示：數據來源為 Yahoo Finance，盤中可能有 15 分鐘延遲。量能倍數 > 1.0 代表今日成交量大於過去 5 日均量。")
    else:
        st.warning("找不到股票數據，請確認代號是否正確。")

else:
    st.info("請在左側輸入股票代號開始分析。")
