# 台灣天氣 (Weather TW)

極簡、優雅、台灣本島及離島 368 鄉鎮市區的天氣 Web / PWA 應用程式。

- **線上網址**：[https://weather-tw.pages.dev](https://weather-tw.pages.dev)
- **部署平台**：Cloudflare Pages
- **資料來源**：交通部中央氣象署（CWA）開放資料平台

---

## 特色功能

1. **秒開體驗（零後端延遲）**：內建預先處理好的全臺鄉鎮天氣快照（SNAP），開啟時不需要再向氣象署查詢，弱網環境也能快速載入。
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

## 自動更新機制

資料更新由三個部分組成：

```
Cloudflare Worker（cron，每 30 分鐘）
   └─ workflow_dispatch(probe=true) ─▶ GitHub Actions（deploy.yml）
        ├─ Probe：向 CWA 要一份資料集，和線上網站的 fingerprint 比對
        ├─ 沒變 ─▶ 結束（約 20 秒，不 build、不部署）
        └─ 有變 ─▶ build_snap.py 重建 SNAP ─▶ wrangler pages deploy
```

- **為什麼由 Cloudflare Worker 觸發**：GitHub Actions 的 `schedule` 會被節流、常常直接丟掉（實測約 33 小時只跑了 6 次，預期約 130 次），不適合當時鐘。Cloudflare Cron Trigger 會準時執行，所以由 `worker/` 這個 Worker 每 30 分鐘呼叫 GitHub 的 `workflow_dispatch`，GitHub 端只負責 probe、build、deploy。
- **更新頻率**：Worker 每 30 分鐘檢查一次，但只有 CWA 真的發布新預報時才會 build 與部署。CWA 約每 3 小時發布一次，所以**網站約每 3 小時更新一次，在 CWA 發布後最多 30 分鐘內上線**。
- **備援**：`deploy.yml` 仍保留每小時一次的 `schedule`，但它只是保險，不依賴它。
- **push 到 `main`**：一律重新抓取資料並部署，不經過 probe。
- **為什麼不用 Pages Deploy Hook**：`weather-tw` 是 direct upload 的 Pages 專案，沒有連接 Git，無法建立 Deploy Hook，所以 build 留在 GitHub Actions。
- **部分鄉鎮缺資料**：CWA 偶爾會讓少數山區鄉鎮缺 3 小時降雨/風速。build 會改用每日預報補降雨、風速顯示「–」，不會因此整份拒絕更新。只有大面積異常（縣市數不足、鄉鎮數減少等）才會拒絕寫入並保留線上舊資料。

---

## CWA API Key 設定

至 [中央氣象署開放資料平台](https://opendata.cwa.gov.tw/) 免費註冊並取得授權碼（API Key，格式為 `CWA-XXXXXXXX-XXXX-XXXX-XXXX-XXXXXXXXXXXX`）。

### 1. 本地開發環境
建立 `.env` 檔案：
```bash
CWA_API_KEY="CWA-XXXXXXXX-XXXX-XXXX-XXXX-XXXXXXXXXXXX"
```

### 2. GitHub Secrets（自動更新排程）
GitHub Actions 的 build 與部署需要：
1. 進入 Repository Settings -> Secrets and variables -> Actions
2. 新增 Repository Secrets：
   - `CWA_API_KEY`：你的 CWA 授權碼
   - `CLOUDFLARE_API_TOKEN`、`CLOUDFLARE_ACCOUNT_ID`：部署 Pages 用

### 3. Cloudflare Worker（準時觸發）
`worker/` 內的 Worker 負責每 30 分鐘叫醒 GitHub Actions：
1. 在 GitHub 建立 fine-grained personal access token：只選這個 repo，權限 **Actions: Read and write**。
2. 部署 Worker 並設定 secret：
   ```bash
   cd worker
   npx wrangler deploy
   npx wrangler secret put GITHUB_TOKEN
   ```
3. 排程寫在 `worker/wrangler.toml` 的 `crons`。token 到期後 Worker 會停止觸發，請記得更新。

### 4. Cloudflare Pages 部署環境變數
在 Cloudflare Dashboard：
1. 前往 **Workers & Pages** -> **weather-tw** -> **Settings** -> **Environment variables**
2. 新增 `CWA_API_KEY`。

---

## 專案結構

```
weather-tw/
├── index.html              # 主程式（含樣式、全臺 368 鄉鎮 SNAP 資料與前端互動）
├── manifest.webmanifest    # PWA Web App Manifest
├── sw.js                   # 只用來清除舊裝置上已安裝的離線快取後自我移除（頁面已不再註冊 Service Worker）
├── favicon.svg             # SVG Favicon
├── favicon-16.png          # 16x16 PNG Favicon
├── favicon-32.png          # 32x32 PNG Favicon
├── icon-192.png            # 192x192 PWA Icon
├── icon-512.png            # 512x512 PWA Icon
├── icon-maskable-512.png   # 512x512 PWA Maskable Icon
├── apple-touch-icon.png    # iOS 桌面圖示
├── fonts/                  # 源樣明體（GenYoMin）Web 字型
├── worker/
│   ├── wrangler.toml       # Cloudflare Worker（cron 每 30 分鐘觸發部署流程）
│   └── src/index.js
├── scripts/
│   ├── fetch_cwa.py        # CWA API 連線測試
│   └── build_snap.py       # 抓取 CWA 全臺 368 鄉鎮預報並重建 index.html 內的 SNAP
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
