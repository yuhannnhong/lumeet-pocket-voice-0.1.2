# Pocket Voice × Operit（Android）

2026-10-22 涵寶在 Redmi 14C 上實測跑通：Operit 自帶的 Ubuntu 終端機跑 Pocket Voice，Operit 的語音直接用克隆聲音念。不用裝 Termux。

Operit 內建 Ubuntu 24.04 ARM64（PRoot）、Python 3.12，跟 Termux 那套的 Ubuntu 一樣，`setup.sh` 直接能用。模型載入約 27 秒。

## 1. 安裝（Operit 終端機）

```
curl -fsSL https://pub-10ca59f0823f4734a9938c42076890d3.r2.dev/v1/setup.sh | PIP_INDEX_URL=https://pypi.org/simple sh
```

- Operit 的 pip 預設用清華鏡像站，台灣連不上會逾時；加 `PIP_INDEX_URL=https://pypi.org/simple` 改官方站。大陸用戶拿掉這段，用清華站反而快。
- 斷掉重跑同一行，會接著裝。
- 小米 HyperOS：Operit 省電設「無限制」、開發者選項開「停止限制子程序」，安裝時畫面停在 Operit 別切走，不然會被系統殺掉。手機只有 4 GB 的話，先把 Termux 和其他 App 關掉。

## 2. 開伺服器（第一個分頁，別關）

```
sh ~/pv/pocket-voice/run.sh 你的密碼
```

看到 `Uvicorn running on http://127.0.0.1:7860` 就好。

## 3. 聲音

**最簡單**：把聲音檔改成英文檔名（例如 `cenxu.mp3`），丟進手機的「下載/PocketVoice」資料夾，重開伺服器就自動建好，聲線代碼就是檔名 `cenxu`。

或者手動上傳（按 ＋ 開新分頁）：

Operit 的 Ubuntu 看得到手機的 `/sdcard`。中文檔名先複製成英文：

```
cp "/sdcard/Download/你的聲音.mp3" ~/voice.mp3
curl -s -F "file=@$HOME/voice.mp3" -F name=我的聲音 -H "Authorization: Bearer 你的密碼" http://127.0.0.1:7860/v1/voices | grep -o '"id":"[^"]*"'
```

記下回傳的 `voice_xxxxxxxx`。

## 4. Operit 語音設定

語音服務設定 → 文本轉語音 → TTS 引擎選 **HTTP API（遠程）**：

| 欄位 | 填 |
|---|---|
| URL 模板 | `http://127.0.0.1:7860/v1/audio/speech`（**http**，不是 https） |
| API 密鑰 | 你的密碼（Operit 會自己加 `Bearer`） |
| HTTP 頭部 | `{}` |
| HTTP 方法 | `POST` |
| Content-Type | `application/json` |
| 請求體 | `{"input":"{text}","voice":"voice_xxxxxxxx","response_format":"mp3"}` |
| 響應處理管線 | `[]` |

HTTP API 這項沒有音色欄位，聲音代碼直接寫在請求體裡。請求體整格只能有這一行。

## 遇到的錯誤

- `Unable to parse TLS packet header`／伺服器一直印 `Invalid HTTP request received`：URL 寫成 https 了。
- `HTTP 422 ... JSON decode error ... Extra data`：請求體後面多了東西（預設的 `{}`、多一個 `}`）。
