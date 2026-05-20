from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import requests
from bs4 import BeautifulSoup
import re
import json
import os
from functools import lru_cache
import time

app = FastAPI(title="台股 ETF API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

FINMIND_TOKEN = os.environ.get("FINMIND_TOKEN", "")
FINMIND_URL = "https://api.finmindtrade.com/api/v4"
TWSE_URL = "https://openapi.twse.com.tw/v1"

# ─────────────────────────────────────────
# 工具函式
# ─────────────────────────────────────────

def finmind_headers():
    return {"Authorization": f"Bearer {FINMIND_TOKEN}"}

def safe_float(val, default=0.0):
    try:
        return float(val)
    except (ValueError, TypeError):
        return default

# ─────────────────────────────────────────
# 路由 1：取得所有台股 ETF 清單 + 漲跌
# ─────────────────────────────────────────

@app.get("/etf/list")
def get_etf_list():
    """
    回傳所有台股 ETF 的即時漲跌資料
    資料來源：台灣證交所 Open API
    """
    try:
        # 從證交所抓當日 ETF 交易資料
        res = requests.get(
            f"{TWSE_URL}/ETF/DAY_TRADING",
            timeout=10
        )
        res.raise_for_status()
        data = res.json()

        etf_list = []
        for item in data:
            code = item.get("Code", "")
            name = item.get("Name", "")
            close = safe_float(item.get("ClosingPrice", 0))
            yesterday = safe_float(item.get("YesterdayPrice", 0))
            change = round(close - yesterday, 2) if close and yesterday else 0
            change_pct = round((change / yesterday) * 100, 2) if yesterday else 0

            etf_list.append({
                "code": code,
                "name": name,
                "price": close,
                "change": change,
                "change_pct": change_pct,
                "volume": item.get("TradeVolume", "0"),
                "open": safe_float(item.get("OpeningPrice", 0)),
                "high": safe_float(item.get("HighestPrice", 0)),
                "low": safe_float(item.get("LowestPrice", 0)),
            })

        return {"success": True, "count": len(etf_list), "data": etf_list}

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"取得 ETF 清單失敗：{str(e)}")


# ─────────────────────────────────────────
# 路由 2：取得特定 ETF 的成分股
# ─────────────────────────────────────────

@app.get("/etf/{etf_code}/holdings")
def get_etf_holdings(etf_code: str):
    """
    回傳指定 ETF 的成分股清單與各成分股漲跌
    資料來源：Yahoo Finance（成分股）+ FinMind（股價）
    """
    # 步驟 1：從 Yahoo Finance 爬成分股
    holdings = fetch_holdings_from_yahoo(etf_code)
    if not holdings:
        raise HTTPException(status_code=404, detail=f"找不到 {etf_code} 的成分股資料")

    # 步驟 2：從 FinMind 抓每檔成分股的即時股價
    stock_ids = [h["ticker"] for h in holdings if h.get("ticker")]
    prices = fetch_prices_from_finmind(stock_ids)

    # 步驟 3：合併資料
    result = []
    for h in holdings:
        ticker = h.get("ticker", "")
        price_info = prices.get(ticker, {})
        yesterday = safe_float(price_info.get("yesterday_price", 0))
        close = safe_float(price_info.get("close", 0))
        change = round(close - yesterday, 2) if close and yesterday else 0
        change_pct = round((change / yesterday) * 100, 2) if yesterday else 0

        result.append({
            "ticker": ticker,
            "name": h.get("name", ""),
            "weight": h.get("weight", 0),
            "price": close,
            "change": change,
            "change_pct": change_pct,
        })

    return {
        "success": True,
        "etf_code": etf_code.upper(),
        "count": len(result),
        "data": result,
    }


# ─────────────────────────────────────────
# 內部函式：Yahoo Finance 爬成分股
# ─────────────────────────────────────────

def fetch_holdings_from_yahoo(etf_code: str):
    url = f"https://tw.stock.yahoo.com/quote/{etf_code}.TW/holding"
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0.0.0 Safari/537.36"
        )
    }
    try:
        res = requests.get(url, headers=headers, timeout=15)
        soup = BeautifulSoup(res.content, "html.parser")
        script = soup.find("script", string=re.compile("root.App.main"))
        if not script:
            return []

        raw = re.search(r"root\.App\.main\s+=\s+(\{.*\})", script.text)
        if not raw:
            return []

        data_str = raw.group(1)
        segments = re.findall(r"\[(.*?)\]", data_str, re.I | re.M)

        for seg in segments:
            if "ticker" in seg and "weighting" in seg:
                holdings_raw = json.loads("[" + seg + "]")
                return [
                    {
                        "ticker": item.get("ticker", "").replace(".TW", ""),
                        "name": item.get("name", ""),
                        "weight": safe_float(item.get("weighting", 0)),
                    }
                    for item in holdings_raw
                ]
    except Exception:
        pass
    return []


# ─────────────────────────────────────────
# 內部函式：FinMind 抓即時股價
# ─────────────────────────────────────────

def fetch_prices_from_finmind(stock_ids: list) -> dict:
    if not stock_ids or not FINMIND_TOKEN:
        return {}
    try:
        # FinMind 支援一次查多檔
        res = requests.get(
            f"{FINMIND_URL}/taiwan_stock_tick_snapshot",
            headers=finmind_headers(),
            params={"data_id": stock_ids},
            timeout=15,
        )
        data = res.json().get("data", [])
        return {item["stock_id"]: item for item in data}
    except Exception:
        return {}


# ─────────────────────────────────────────
# 路由 3：健康檢查
# ─────────────────────────────────────────

@app.get("/")
def health_check():
    return {"status": "ok", "message": "台股 ETF API 運行中 🟢"}
