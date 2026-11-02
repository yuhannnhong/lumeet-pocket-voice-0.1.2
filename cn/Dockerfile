# Pocket Voice 国内版：阿里云函数计算（FC）、腾讯云云托管等国内云用这份
# 跟 server/Dockerfile 的差别：基础镜像、pip、模型都走国内镜像，不用连 GitHub / Docker Hub / Hugging Face
# 构建上下文是仓库根目录：docker build -f cn/Dockerfile .
FROM docker.m.daocloud.io/library/python:3.12-slim

ENV PIP_INDEX_URL=https://pypi.tuna.tsinghua.edu.cn/simple \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    HF_ENDPOINT=https://hf-mirror.com \
    HF_HUB_DISABLE_TELEMETRY=1

WORKDIR /app
COPY server/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 模型在构建时下载好（约 730 MB），启动不用再等
RUN hf download OpenMOSS-Team/MOSS-TTS-Nano-100M-ONNX --local-dir /app/models/MOSS-TTS-Nano-100M-ONNX \
    && hf download OpenMOSS-Team/MOSS-Audio-Tokenizer-Nano-ONNX --local-dir /app/models/MOSS-Audio-Tokenizer-Nano-ONNX \
    && rm -rf /root/.cache

# MOSS-TTS-Nano 的 ONNX 推理代码（Apache-2.0，见 cn/moss/LICENSE），直接放在仓库里，不用连 GitHub
COPY cn/moss /opt/moss
COPY server/app.py server/pocket_voice.py ./

ENV PYTHONPATH=/opt/moss \
    MODEL_DIR=/app/models \
    VOICES_DIR=/tmp/voices \
    CPU_THREADS=2

EXPOSE 7860
CMD ["sh", "-c", "exec uvicorn app:app --host 0.0.0.0 --port ${PORT:-7860}"]
