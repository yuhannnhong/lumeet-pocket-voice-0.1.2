"""Pocket Voice 伺服器：OpenAI 相容的 /v1/audio/speech，加上建立聲線的 /v1/voices。規格見 docs/API.md。

環境變數：
  POCKET_VOICE_TOKEN  必填。請求要帶 Authorization: Bearer <token>，沒設就拒絕所有請求
  MODEL_DIR           模型資料夾，預設 models（裡面放兩個 ONNX 模型）
  CPU_THREADS         預設 2
  VOICES_DIR          聲線存放處，預設 voices（免費 Space 重啟會清空，所以建立時也把代碼回傳給用戶端保存）
  VOICE_INBOX         選填。開機時把這個資料夾裡的音檔自動建成聲線，檔名就是聲線代碼（cenxu.mp3 → cenxu）
  DEFAULT_VOICE       選填。MCP（Claude 官方 App）沒指定聲線時用哪一個，填聲線代碼
  VOICE_SAMPLE_URL    選填。MCP 要用、但伺服器上還沒有聲線時，從這個網址下載聲音樣本建成聲線 default
  PUBLIC_BASE_URL     選填。語音連結的網址開頭，不填就用請求的網址
"""

from __future__ import annotations

import hmac
import json
import logging
import os
import re
import threading
import time
import urllib.request
import uuid
from pathlib import Path

from fastapi import Depends, FastAPI, File, Form, Header, HTTPException, Request, UploadFile
from starlette.concurrency import run_in_threadpool
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, Response
from pydantic import BaseModel

from pocket_voice import OUTPUT_SAMPLE_RATE, PocketVoice, encode_audio

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


# ─── MCP：給 Claude 官方 App（claude.ai 自訂連接器）用 ─────────────────────
# 網址 /mcp/<POCKET_VOICE_TOKEN>，密碼放在路徑裡（自訂連接器不能加標頭）。
# 官方 App 不能即時通話，所以做成「語音條」：念好存成 mp3，回一個 10 分鐘內有效的播放連結。

DEFAULT_VOICE = os.environ.get("DEFAULT_VOICE", "")
VOICE_SAMPLE_URL = os.environ.get("VOICE_SAMPLE_URL", "")
PUBLIC_BASE_URL = os.environ.get("PUBLIC_BASE_URL", "").rstrip("/")
CLIP_TTL = 600
CLIP_MAX = 30
clips: dict[str, tuple[bytes, float]] = {}
clips_lock = threading.Lock()
sample_lock = threading.Lock()

MCP_TOOLS = [
    {
        "name": "speak",
        "description": (
            "用你自己的聲音把一段話念出來，回傳一個語音條連結（mp3，10 分鐘內有效）。"
            "想讓對方聽到你的聲音時用：把連結原樣放進回覆，對方點開就能聽。一次最多 500 字，短一點比較快。"
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "text": {"type": "string", "description": "要念的話（中文為主，不要放動作描述或表情符號）"},
                "voice": {"type": "string", "description": "聲線代碼，不填就用預設聲線"},
            },
            "required": ["text"],
        },
    },
    {
        "name": "list_voices",
        "description": "列出伺服器上有哪些聲線（代碼和名字）。",
        "inputSchema": {"type": "object", "properties": {}},
    },
]


def ensure_sample_voice(eng: PocketVoice) -> None:
    """雲端重啟會清空聲線；有設 VOICE_SAMPLE_URL 的話，第一次要用時下載樣本建成 default。"""
    if "default" in voices or not VOICE_SAMPLE_URL:
        return
    with sample_lock:
        if "default" in voices:
            return
        with urllib.request.urlopen(VOICE_SAMPLE_URL, timeout=30) as r:
            data = r.read(MAX_UPLOAD_BYTES + 1)
        if len(data) > MAX_UPLOAD_BYTES:
            raise ValueError("聲音樣本太大，請小於 8 MB")
        codes, seconds = eng.create_profile(data)
        v = {"id": "default", "name": "default", "seconds": round(seconds, 1),
             "created_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "codes": codes}
        voices["default"] = v
        (VOICES_DIR / "default.json").write_text(json.dumps(v))


def pick_voice(eng: PocketVoice, wanted: str) -> dict:
    ensure_sample_voice(eng)
    for vid in (wanted, DEFAULT_VOICE, "default"):
        if vid and vid in voices:
            return voices[vid]
    if wanted:
        raise ValueError(f"找不到聲線 {wanted}，可以先用 list_voices 看有哪些")
    if voices:
        return next(iter(voices.values()))
    raise ValueError("伺服器上還沒有聲線：先用 Lumeet 上傳一次聲音樣本，或在部署時設定 VOICE_SAMPLE_URL")


def keep_clip(body: bytes) -> str:
    cid = uuid.uuid4().hex
    now = time.time()
    with clips_lock:
        for k in [k for k, (_, exp) in clips.items() if exp < now]:
            clips.pop(k, None)
        while len(clips) >= CLIP_MAX:
            clips.pop(next(iter(clips)))
        clips[cid] = (body, now + CLIP_TTL)
    return cid


def base_url(request: Request) -> str:
    if PUBLIC_BASE_URL:
        return PUBLIC_BASE_URL
    proto = request.headers.get("x-forwarded-proto", request.url.scheme).split(",")[0].strip()
    host = request.headers.get("x-forwarded-host") or request.headers.get("host") or request.url.netloc
    return f"{proto}://{host}"


def run_tool(name: str, args: dict, request: Request) -> dict:
    eng = ready()
    if name == "list_voices":
        items = [f"{v['id']}（{v['name']}，樣本 {v['seconds']} 秒）" for v in voices.values()]
        return {"content": [{"type": "text", "text": "\n".join(items) or "還沒有聲線"}]}
    if name != "speak":
        raise ValueError(f"沒有這個工具：{name}")
    text = str(args.get("text", "")).strip()
    if not text:
        raise ValueError("沒有要念的字")
    if len(text) > MAX_TEXT_CHARS:
        raise ValueError(f"一次最多 {MAX_TEXT_CHARS} 字，請分段")
    v = pick_voice(eng, str(args.get("voice") or ""))
    mono, timing = eng.synthesize(text, v["codes"])
    body, _ = encode_audio(mono, "mp3")
    url = f"{base_url(request)}/audio/{keep_clip(body)}.mp3"
    note = f"（約 {len(mono) / OUTPUT_SAMPLE_RATE:.1f} 秒）"
    return {"content": [{"type": "text", "text": f"語音條{note}：{url}\n把這個連結原樣放進回覆，對方點開就能聽。10 分鐘內有效。"}]}


def rpc_result(mid, result: dict) -> dict:
    return {"jsonrpc": "2.0", "id": mid, "result": result}


def rpc_error(mid, code: int, message: str) -> dict:
    return {"jsonrpc": "2.0", "id": mid, "error": {"code": code, "message": message}}


async def handle_rpc(msg: dict, request: Request) -> dict | None:
    mid, method, params = msg.get("id"), msg.get("method", ""), msg.get("params") or {}
    if mid is None:  # 通知（notifications/initialized 之類），不用回
        return None
    if method == "initialize":
        return rpc_result(mid, {
            "protocolVersion": params.get("protocolVersion") or "2025-06-18",
            "capabilities": {"tools": {}},
            "serverInfo": {"name": "pocket-voice", "version": "0.1.2"},
            "instructions": "Pocket Voice：用 speak 把你想說的話念成語音條，連結原樣放進回覆。",
        })
    if method == "ping":
        return rpc_result(mid, {})
    if method == "tools/list":
        return rpc_result(mid, {"tools": MCP_TOOLS})
    if method == "tools/call":
        try:
            out = await run_in_threadpool(run_tool, params.get("name", ""), params.get("arguments") or {}, request)
        except HTTPException as exc:
            detail = exc.detail if isinstance(exc.detail, dict) else {"message": str(exc.detail)}
            out = {"content": [{"type": "text", "text": detail.get("message", "出錯了")}], "isError": True}
        except Exception as exc:
            logging.exception("mcp tool failed")
            out = {"content": [{"type": "text", "text": str(exc)}], "isError": True}
        return rpc_result(mid, out)
    return rpc_error(mid, -32601, f"不支援 {method}")


@app.post("/mcp/{token}")
async def mcp(token: str, request: Request) -> Response:
    if not TOKEN or not hmac.compare_digest(token, TOKEN):
        raise error(401, "unauthorized", "token 不對")
    try:
        payload = await request.json()
    except Exception:
        return JSONResponse(status_code=400, content=rpc_error(None, -32700, "不是正確的 JSON"))
    if isinstance(payload, list):
        replies = [r for r in [await handle_rpc(m, request) for m in payload] if r is not None]
        return JSONResponse(replies) if replies else Response(status_code=202)
    reply = await handle_rpc(payload, request)
    return JSONResponse(reply) if reply is not None else Response(status_code=202)


@app.get("/mcp/{token}")
def mcp_get(token: str) -> Response:
    # 不提供伺服器主動推送的串流
    return Response(status_code=405, headers={"Allow": "POST"})


@app.get("/audio/{clip}.mp3")
def audio(clip: str) -> Response:
    with clips_lock:
        item = clips.get(clip)
    if not item or item[1] < time.time():
        raise error(404, "clip_expired", "這段語音過期了（10 分鐘內有效）")
    return Response(content=item[0], media_type="audio/mpeg", headers={"Cache-Control": "private, max-age=600"})
