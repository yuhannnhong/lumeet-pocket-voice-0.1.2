"""Pocket Voice 伺服器：OpenAI 相容的 /v1/audio/speech，加上建立聲線的 /v1/voices。規格見 docs/API.md。

環境變數：
  POCKET_VOICE_TOKEN  必填。請求要帶 Authorization: Bearer <token>，沒設就拒絕所有請求
  MODEL_DIR           模型資料夾，預設 models（裡面放兩個 ONNX 模型）
  CPU_THREADS         預設 2
  VOICES_DIR          聲線存放處，預設 voices（免費 Space 重啟會清空，所以建立時也把代碼回傳給用戶端保存）
  VOICE_INBOX         選填。開機時把這個資料夾裡的音檔自動建成聲線，檔名就是聲線代碼（cenxu.mp3 → cenxu）
"""

from __future__ import annotations

import hmac
import json
import logging
import os
import re
import time
import uuid
from pathlib import Path

from fastapi import Depends, FastAPI, File, Form, Header, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, Response
from pydantic import BaseModel

from pocket_voice import PocketVoice, encode_audio

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")

TOKEN = os.environ.get("POCKET_VOICE_TOKEN", "")
MODEL_DIR = os.environ.get("MODEL_DIR", "models")
VOICES_DIR = Path(os.environ.get("VOICES_DIR", "voices"))
VOICE_INBOX = os.environ.get("VOICE_INBOX", "")
AUDIO_EXTS = {".mp3", ".wav", ".flac", ".ogg"}
MAX_TEXT_CHARS = 500
MAX_UPLOAD_BYTES = 8 * 1024 * 1024

app = FastAPI(title="Pocket Voice")
# Lumeet 網頁版直接從瀏覽器呼叫，所以開 CORS；靠 token 擋人
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["GET", "POST", "DELETE"],
    allow_headers=["Authorization", "Content-Type"],
    expose_headers=["X-Pocket-Voice-Timing"],
)

# 手機本地版（伺服器跑在 127.0.0.1）：Chrome 從 https 網頁連本機要先問「可以連區域網路嗎」，這裡回可以
@app.middleware("http")
async def allow_private_network(request, call_next):
    response = await call_next(request)
    if request.headers.get("access-control-request-private-network"):
        response.headers["Access-Control-Allow-Private-Network"] = "true"
    return response


engine: PocketVoice | None = None
voices: dict[str, dict] = {}


def error(status: int, code: str, message: str) -> HTTPException:
    return HTTPException(status_code=status, detail={"code": code, "message": message})


@app.exception_handler(HTTPException)
async def http_error(_request, exc: HTTPException):
    detail = exc.detail if isinstance(exc.detail, dict) else {"code": "error", "message": str(exc.detail)}
    return JSONResponse(status_code=exc.status_code, content={"error": detail})


def auth(authorization: str = Header(default="")) -> None:
    given = authorization.removeprefix("Bearer ").strip()
    if not TOKEN or not hmac.compare_digest(given, TOKEN):
        raise error(401, "unauthorized", "token 不對")


def ready() -> PocketVoice:
    if engine is None:
        raise error(503, "model_loading", "模型還在載入，稍後再試")
    return engine


@app.on_event("startup")
def load() -> None:
    global engine
    VOICES_DIR.mkdir(parents=True, exist_ok=True)
    for f in VOICES_DIR.glob("*.json"):
        try:
            v = json.loads(f.read_text())
            voices[v["id"]] = v
        except Exception:  # 壞掉的檔案略過
            logging.warning("skip broken voice file %s", f)
    engine = PocketVoice(MODEL_DIR, threads=int(os.environ.get("CPU_THREADS", "2")))
    load_inbox(engine)


def load_inbox(eng: PocketVoice) -> None:
    """丟進 VOICE_INBOX 的音檔，開機時自動建成聲線，不用另外打指令上傳。已經建過的跳過。"""
    inbox = Path(VOICE_INBOX) if VOICE_INBOX else None
    if not inbox or not inbox.is_dir():
        return
    for f in sorted(inbox.iterdir()):
        if f.suffix.lower() not in AUDIO_EXTS:
            continue
        vid = re.sub(r"[^a-z0-9_-]", "", f.stem.lower())[:40] or "voice"
        if vid in voices:
            continue
        try:
            codes, seconds = eng.create_profile(f.read_bytes())
        except Exception as exc:  # 讀不了的檔案跳過，不擋開機
            logging.warning("skip inbox file %s: %s", f.name, exc)
            continue
        v = {"id": vid, "name": f.stem[:40], "seconds": round(seconds, 1),
             "created_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "codes": codes}
        voices[vid] = v
        (VOICES_DIR / f"{vid}.json").write_text(json.dumps(v))
        logging.info("inbox voice ready: %s (%.1fs)", vid, seconds)


@app.get("/health")
def health() -> dict:
    return {"ok": True, "model": "moss-tts-nano-100m-onnx", "loaded": engine is not None, "voices": len(voices), "auth": bool(TOKEN)}


def public(v: dict, with_codes: bool = False) -> dict:
    out = {k: v[k] for k in ("id", "name", "seconds", "created_at")}
    if with_codes:
        out["codes"] = v["codes"]
    return out


@app.post("/v1/voices", dependencies=[Depends(auth)])
async def create_voice(file: UploadFile = File(...), name: str = Form("")) -> dict:
    eng = ready()
    data = await file.read()
    if len(data) > MAX_UPLOAD_BYTES:
        raise error(413, "audio_too_large", "參考音檔太大，請小於 8 MB")
    try:
        codes, seconds = eng.create_profile(data)
    except Exception as exc:
        raise error(400, "bad_audio", f"讀不了這個音檔：{exc}") from exc
    if seconds < 3:
        raise error(400, "audio_too_short", "參考音至少要 3 秒")
    v = {
        "id": "voice_" + uuid.uuid4().hex[:12],
        "name": name.strip()[:40] or "未命名",
        "seconds": round(seconds, 1),
        "created_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "codes": codes,
    }
    voices[v["id"]] = v
    (VOICES_DIR / f"{v['id']}.json").write_text(json.dumps(v))
    # 代碼也回傳：用戶端自己存一份，伺服器重啟清空了也能直接用
    return public(v, with_codes=True)


@app.get("/v1/voices", dependencies=[Depends(auth)])
def list_voices() -> dict:
    return {"data": [public(v) for v in voices.values()]}


@app.delete("/v1/voices/{voice_id}", dependencies=[Depends(auth)])
def delete_voice(voice_id: str) -> dict:
    if voices.pop(voice_id, None) is None:
        raise error(404, "voice_not_found", "找不到這個聲線")
    (VOICES_DIR / f"{voice_id}.json").unlink(missing_ok=True)
    return {"deleted": voice_id}


class SpeechRequest(BaseModel):
    input: str
    voice: str | None = None
    voice_codes: list[list[int]] | None = None  # 用戶端自己存的聲音代碼，伺服器沒有這個聲線時用
    model: str | None = None
    response_format: str = "mp3"
    seed: int | None = None


@app.post("/v1/audio/speech", dependencies=[Depends(auth)])
def speech(req: SpeechRequest) -> Response:
    eng = ready()
    text = req.input.strip()
    if not text:
        raise error(400, "empty_text", "沒有要唸的字")
    if len(text) > MAX_TEXT_CHARS:
        raise error(400, "text_too_long", f"一次最多 {MAX_TEXT_CHARS} 字")
    codes = voices.get(req.voice or "", {}).get("codes") or req.voice_codes
    if not codes:
        raise error(404, "voice_not_found", "找不到這個聲線")
    fmt = req.response_format if req.response_format in ("mp3", "wav", "pcm") else "mp3"
    mono, timing = eng.synthesize(text, codes, seed=req.seed)
    body, mime = encode_audio(mono, fmt)
    return Response(content=body, media_type=mime, headers={"X-Pocket-Voice-Timing": json.dumps(timing)})
