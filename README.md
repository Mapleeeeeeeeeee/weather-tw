# 台灣天氣 (Weather TW)

極簡、優雅、台灣本島及離島 368 鄉鎮市區的天氣 Web / PWA 應用程式。

- **線上網址**：[https://weather-tw.pages.dev](https://weather-tw.pages.dev)
- **部署平台**：Cloudflare Pages
- **資料來源**：交通部中央氣象署（CWA）開放資料平台

---

## 特色功能

1. **秒開體驗（零後端延遲）**：內建預先處理好的全臺鄉鎮天氣快照（SNAP），離線或弱網環境也能瞬間載入。
2. **直覺生活指標**：以白話自然語言提示「帶傘建議」、「體感溫度」、「舒適度與穿搭」及高低溫差。
3. **逐時與一週趨勢**：未來 24 小時逐時降雨機率、氣溫曲線，以及未來一週天氣走勢。
4. **全臺 368 鄉鎮切換**：快速搜尋與常用地區雙生活圈記憶（儲存於 LocalStorage）。
5. **完整 PWA 支援**：黃昏與晴多雲配色圖示（自適應 Maskable Icon、Apple Touch Icon、Web Manifest），可直接「加入主畫面」當作原生 App 使用。

---

## 中央氣象署 (CWA) 更新頻率

中央氣象署開放資料 API 各資料集有不同的發布節奏：

| 資料集代碼 | 資料集名稱 | 涵蓋範圍 | CWA 發布/更新頻率 |
| :--- | :--- | :--- | :--- |
| **F-D0047-001 ~ 087** | 各縣市鄉鎮天氣預報（未來 3 天逐 3 小時） | 全臺 22 縣市各鄉鎮 | **每 3 小時更新一次**<br>（02:00, 05:00, 08:00, 11:00, 14:00, 17:00, 20:00, 23:00） |
| **F-D0047-003 ~ 087** | 各縣市鄉鎮未來 1 週天氣預報 | 全臺 22 縣市各鄉鎮 | **每天發布 2～3 次**<br>（約 05:00、11:00、17:00） |
| **F-C0032-001** | 一般天氣預報（今明 36 小時天氣預報） | 22 縣市概況 | **每天發布 3 次**<br>（05:00、11:00、17:00） |
| **O-A0001-001 / O-A0003-001** | 即時氣象觀測資料（局屬站 / 自動站） | 各地面測站 | **每 10 分鐘 ~ 1 小時更新一次** |

> [!TIP]
> **建議更新排程**：
> 若設定自動排程抓取最新預報，最建議的頻率是 **每 3 小時**（或每天 4 次重點更新：`05:30`、`11:30`、`17:30`、`23:30`）。這樣能完美對齊 CWA F-D0047 的預報產出時間，既保持最新，又避免頻繁呼叫遭 Rate Limit。

---

## CWA API Key 設定

至 [中央氣象署開放資料平台](https://opendata.cwa.gov.tw/) 免費註冊並取得授權碼（API Key，格式為 `CWA-XXXXXXXX-XXXX-XXXX-XXXX-XXXXXXXXXXXX`）。

### 1. 本地開發環境
建立 `.env` 檔案：
```bash
CWA_API_KEY="CWA-XXXXXXXX-XXXX-XXXX-XXXX-XXXXXXXXXXXX"
```

### 2. GitHub Secrets（自動更新排程）
若使用 GitHub Actions 自動更新天氣資料：
1. 進入 Repository Settings -> Secrets and variables -> Actions
2. 新增 Repository Secret：
   - Name: `CWA_API_KEY`
   - Value: `你的授權碼`

### 3. Cloudflare Pages 部署環境變數
在 Cloudflare Dashboard：
1. 前往 **Workers & Pages** -> **weather-tw** -> **Settings** -> **Environment variables**
2. 新增 `CWA_API_KEY`。

---

## 專案結構

```
weather-tw/
├── index.html              # 主程式（含樣式、全臺 368 鄉鎮 SNAP 資料與前端互動）
├── manifest.webmanifest    # PWA Web App Manifest
├── sw.js                   # Service Worker（離線快取）
├── favicon.svg             # SVG Favicon
├── favicon-16.png          # 16x16 PNG Favicon
├── favicon-32.png          # 32x32 PNG Favicon
├── icon-192.png            # 192x192 PWA Icon
├── icon-512.png            # 512x512 PWA Icon
├── icon-maskable-512.png   # 512x512 PWA Maskable Icon
├── apple-touch-icon.png    # iOS 桌面圖示
├── fonts/                  # 源樣明體（GenYoMin）Web 字型
├── scripts/
│   └── fetch_cwa.py        # CWA API 抓取與更新輔助腳本
└── README.md
```

---

## 本地執行與部署

### 本地預覽
直接透過任何靜態檔案伺服器開啟：
```bash
# Python
python3 -m http.server 8080

# 或 Node.js
npx serve .
```

### 部署到 Cloudflare Pages
```bash
npx wrangler pages deploy . --project-name=weather-tw
```
