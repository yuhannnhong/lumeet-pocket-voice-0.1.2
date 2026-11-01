# Pocket Voice 伺服器。Hugging Face Space（Docker）、F1、Mac、雲主機都用這份。
FROM python:3.12-slim

RUN apt-get update && apt-get install -y --no-install-recommends git \
    && rm -rf /var/lib/apt/lists/*

# MOSS-TTS-Nano 的 ONNX runtime（Apache-2.0），固定版本
ARG MOSS_COMMIT=8b7bcc9341b3b4ef3a3a58ba1338a7d85ff133eb
RUN git clone https://github.com/OpenMOSS/MOSS-TTS-Nano /opt/moss \
    && git -C /opt/moss checkout ${MOSS_COMMIT} \
    && rm -rf /opt/moss/.git /opt/moss/assets /opt/moss/finetuning /opt/moss/examples

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 模型在建置時下載好（約 730 MB），啟動不用再等
RUN hf download OpenMOSS-Team/MOSS-TTS-Nano-100M-ONNX --local-dir /app/models/MOSS-TTS-Nano-100M-ONNX \
    && hf download OpenMOSS-Team/MOSS-Audio-Tokenizer-Nano-ONNX --local-dir /app/models/MOSS-Audio-Tokenizer-Nano-ONNX

COPY app.py pocket_voice.py ./

ENV PYTHONPATH=/opt/moss \
    MODEL_DIR=/app/models \
    VOICES_DIR=/tmp/voices \
    CPU_THREADS=2

# Hugging Face Space 用 7860；Cloud Run 會給 PORT（預設 8080），有給就聽它的
EXPOSE 7860
CMD ["sh", "-c", "exec uvicorn app:app --host 0.0.0.0 --port ${PORT:-7860}"]
