---
title: Pocket Voice
emoji: 🎙️
colorFrom: yellow
colorTo: gray
sdk: docker
app_port: 7860
pinned: false
license: apache-2.0
---

# Pocket Voice（Hugging Face Space）

> **2026-11 實測：Hugging Face 免費的 CPU basic 已經不能用了**，要選付費硬體才跑得起來。沒有付費的話，請改用自己的電腦（見根目錄 README「iPhone 连电脑」）。

這個 Space 跑的就是 `server/`：匯入一次聲音樣本，之後把任意中文唸成同一個聲音。模型是 [MOSS-TTS-Nano](https://github.com/OpenMOSS/MOSS-TTS-Nano)（Apache-2.0）。

## 怎麼建立（給沒有小電腦的用戶）

1. 註冊 Hugging Face，右上角 **New → Space**。
2. 名字隨意，**SDK 選 Docker**，模板選 **Blank**，硬體選付費的 CPU（免費 CPU basic 已不能用），**Visibility 選 Private**。
3. 建好後到 **Files → Add file → Upload files**，上傳這五個檔：
   - 這份 `README.md`（覆蓋原本的）
   - `server/Dockerfile`
   - `server/requirements.txt`
   - `server/app.py`
   - `server/pocket_voice.py`
4. 到 **Settings → Variables and secrets → New secret**：名字 `POCKET_VOICE_TOKEN`，值自己想一串長一點的密碼。Lumeet 連線時要填同一串。
5. 回 **App** 分頁等它建置（第一次大約 10 分鐘，要下載模型）。看到 Running 就好了。

Space 的網址是 `https://<帳號>-<space名稱>.hf.space`，打開 `/health` 看到 `"loaded": true` 就代表模型載好了。

## 注意

- 免費 CPU 是 2 核，一句話大約要等幾秒到十幾秒；拿來傳語音條沒問題，講電話會偏慢。
- 兩天沒用會休眠，醒來的第一句要多等一兩分鐘。
- 免費 Space 重啟會清空伺服器上的聲線，所以建立聲線時會把聲音代碼一起回傳，Lumeet 自己存一份，合成時帶 `voice_codes`，伺服器清空了也能用。
- Space 一定要設成 Private，並設定 `POCKET_VOICE_TOKEN`；沒設 token 的伺服器會拒絕所有請求。
