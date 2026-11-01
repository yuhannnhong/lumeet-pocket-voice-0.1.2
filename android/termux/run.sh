#!/bin/sh
# 啟動 Pocket Voice（手機本地版）。用法：sh run.sh 你的密碼
cd "$(dirname "$0")"
[ -n "$1" ] || { echo "請在後面加上密碼，例如：sh run.sh abc123"; exit 1; }
. venv/bin/activate
# 聲音檔丟進這個資料夾，開機時自動建成聲線（檔名就是聲線代碼，例如 cenxu.mp3 → cenxu）
# 看得到手機儲存空間（Operit）就用「下載/PocketVoice」，不然用 ~/pv/voice-inbox
INBOX=/sdcard/Download/PocketVoice
[ -d /sdcard/Download ] || INBOX="$HOME/pv/voice-inbox"
mkdir -p "$INBOX" 2>/dev/null || INBOX="$HOME/pv/voice-inbox"; mkdir -p "$INBOX"
echo "聲音資料夾：$INBOX"
PYTHONPATH="$PWD/moss" MODEL_DIR="$PWD/models" VOICES_DIR="$PWD/voices" VOICE_INBOX="$INBOX" CPU_THREADS=4 POCKET_VOICE_TOKEN="$1" \
  exec uvicorn app:app --host 127.0.0.1 --port 7860
