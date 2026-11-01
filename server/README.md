# server

電腦或雲端用的 TTS 伺服器，F1、Mac mini、雲主機共用這份。

Python＋ONNX Runtime（CPU，不用 PyTorch），FastAPI 提供 [API 規格](../docs/API.md) 的接口。Docker 版在建置時就把模型下載好。

已實作：`app.py`（FastAPI）、`pocket_voice.py`（引擎＋文字前處理）、`Dockerfile`。本機跑法：

```
pip install -r requirements.txt
git clone https://github.com/OpenMOSS/MOSS-TTS-Nano /opt/moss
hf download OpenMOSS-Team/MOSS-TTS-Nano-100M-ONNX --local-dir models/MOSS-TTS-Nano-100M-ONNX
hf download OpenMOSS-Team/MOSS-Audio-Tokenizer-Nano-ONNX --local-dir models/MOSS-Audio-Tokenizer-Nano-ONNX
PYTHONPATH=/opt/moss POCKET_VOICE_TOKEN=換成你的密碼 uvicorn app:app --port 7860
```
