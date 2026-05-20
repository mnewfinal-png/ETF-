# 台股 ETF 追蹤 API

## 部署到 Railway 步驟

### 1. 安裝 Railway CLI
```
npm install -g @railway/cli
```

### 2. 登入 Railway
```
railway login
```

### 3. 初始化並部署
```
railway init
railway up
```

### 4. 設定環境變數（重要！）
在 Railway Dashboard → Variables 新增：
```
FINMIND_TOKEN=你的FinMind Token貼在這裡
```

---

## API 端點說明

### 取得所有 ETF 清單
```
GET /etf/list
```
回傳範例：
```json
{
  "success": true,
  "count": 250,
  "data": [
    {
      "code": "00878",
      "name": "國泰永續高股息",
      "price": 22.5,
      "change": 0.3,
      "change_pct": 1.35,
      "volume": "123456",
      "open": 22.2,
      "high": 22.6,
      "low": 22.1
    }
  ]
}
```

### 取得特定 ETF 成分股
```
GET /etf/00878/holdings
```
回傳範例：
```json
{
  "success": true,
  "etf_code": "00878",
  "count": 30,
  "data": [
    {
      "ticker": "2330",
      "name": "台積電",
      "weight": 12.5,
      "price": 920.0,
      "change": 10.0,
      "change_pct": 1.1
    }
  ]
}
```

---

## 本機測試方式

安裝套件：
```
pip install -r requirements.txt
```

設定 Token 並啟動：
```
export FINMIND_TOKEN=你的Token
uvicorn main:app --reload
```

開啟 http://localhost:8000 確認運作
開啟 http://localhost:8000/docs 查看所有 API 文件
