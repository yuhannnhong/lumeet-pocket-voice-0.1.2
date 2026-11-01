# 手機本地版（Termux）

不用寫 App，先在 Android 手機上直接跑 `server/`，確認手機跑得動。伺服器只聽 `127.0.0.1`，只有這支手機自己連得到。

下載點（Cloudflare R2，公開，下載不收流量費）：`https://pub-10ca59f0823f4734a9938c42076890d3.r2.dev/v1/`

- `setup.sh`：安裝腳本（這個資料夾的同名檔）
- `pocket-voice-code.tar.gz`：`server/` 的 `app.py`、`pocket_voice.py`、`requirements.txt`（不含 huggingface_hub）、`run.sh`、`models.txt`，加上 MOSS-TTS-Nano 的 runtime 檔（`onnx_tts_runtime.py`、`ort_cpu_runtime.py`、`text_normalization_pipeline.py`、`tts_robust_normalizer_single_script.py`、`moss_tts_nano/`，Apache-2.0）
- `models/…`：int8 量化版（`scripts/quantize_int8.py` 產生），只放合成用得到的檔，約 550 MB

## 最快：一行裝好

在 Termux 裡貼：

```
curl -fsSL https://pub-10ca59f0823f4734a9938c42076890d3.r2.dev/v1/termux.sh | sh
```

會更新 Termux、裝 Ubuntu、跑 `setup.sh`，最後建一個 `pv` 指令。之後啟動只要打 `pv 你的密碼`。

## 分開做（一行裝好失敗時）

1. 裝 Termux：GitHub https://github.com/termux/termux-app/releases 下載 `arm64-v8a` 的 apk（Play 商店的版本太舊）。
2. 開 Termux，依序貼：
   ```
   pkg update -y && pkg upgrade -y
   pkg install -y proot-distro
   proot-distro install ubuntu
   proot-distro login ubuntu
   ```
3. 進到 Ubuntu 之後：
   ```
   apt-get update && apt-get install -y curl
   curl -fsSL https://pub-10ca59f0823f4734a9938c42076890d3.r2.dev/v1/setup.sh | sh
   ```
4. 啟動：`sh ~/pv/pocket-voice/run.sh 你的密碼`。手機瀏覽器開 `http://127.0.0.1:7860/health` 看到 `"loaded":true` 就成功。
5. 不讓系統殺掉：Termux 通知列按「Acquire wakelock」；HyperOS／MIUI 的電池設定把 Termux 改成「無限制」、開「自動啟動」。

聲線用 Lumeet 裡已經存好的聲音代碼（`voice_codes`），手機上不用建聲線（建聲線的瞬間記憶體會衝到 2 GB）。

## 已知數字（雲端 4 核 CPU，不是手機）

int8、2 執行緒：記憶體峰值約 0.95 GB；一句 3～7 秒的話約 3～4 秒生成。手機（例如 Redmi 14C，Helio G81、4 GB）會慢上好幾倍，待實測，結果寫進 `test/`。

## 清掉安裝暫存（2026-10-22）

新版 `setup.sh` 裝完會自己清掉 apt、pip 的暫存。之前裝過的，在 Termux 貼這行（不影響 Pocket Voice）：

```
proot-distro login ubuntu -- sh -c "curl -fsSL https://pub-10ca59f0823f4734a9938c42076890d3.r2.dev/v1/clean.sh | sh"
```
