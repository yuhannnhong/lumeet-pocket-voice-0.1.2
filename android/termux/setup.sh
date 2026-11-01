#!/bin/sh
# Pocket Voice 手機本地版安裝（在 Termux 的 Ubuntu 裡跑）
set -e
BASE=https://pub-10ca59f0823f4734a9938c42076890d3.r2.dev/v1
echo "== 1/4 安裝 Python"
apt-get update -y
DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends python3 python3-venv curl ca-certificates
echo "== 2/4 下載程式"
mkdir -p ~/pv && cd ~/pv
curl -fL $BASE/pocket-voice-code.tar.gz | tar xz
cd pocket-voice
echo "== 3/4 安裝套件（要幾分鐘）"
python3 -m venv venv
. venv/bin/activate
pip install --no-cache-dir --upgrade pip
pip install --no-cache-dir -r requirements.txt
echo "== 4/4 下載模型（約 550 MB，斷了重跑這個腳本會接著下載）"
while read f; do
  mkdir -p "models/$(dirname "$f")"
  curl -fL -C - -o "models/$f" "$BASE/models/$f"
done < models.txt
# 安裝用的暫存清掉（apt 的下載檔和清單、pip 快取），省幾百 MB
apt-get clean
rm -rf /var/lib/apt/lists/* ~/.cache/pip
echo
echo "裝好了！啟動：sh ~/pv/pocket-voice/run.sh 你的密碼"
