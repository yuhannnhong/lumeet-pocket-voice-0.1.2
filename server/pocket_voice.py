"""Pocket Voice 引擎：包住 MOSS-TTS-Nano 的 ONNX runtime。

- 不用 PyTorch：官方 runtime 只在讀參考音檔時用到 torch／torchaudio，這裡改用 soundfile＋scipy。
- 聲線（Voice Profile）只存聲音代碼（幀數 × 16 的整數），合成時不用再分析原音檔。
- 唸之前的文字前處理照 test/2026-10-21-cloud-cpu.md 的定案：繁轉簡、「妳」→「你」、分段、短句合併。
"""

from __future__ import annotations

import io
import logging
import re
import sys
import threading
import time
import types
from math import gcd
from pathlib import Path

import numpy as np
import soundfile as sf
from opencc import OpenCC
from scipy.signal import resample_poly

# 官方 runtime 在模組最上面 import torch／torchaudio，但只有 _load_reference_audio 用到。
# 載入它的那一下先放兩個空模組讓它 import 得過，載完馬上拿掉（scipy 看到 sys.modules 裡有 torch 會當真）；
# 用到 torch 的那個方法下面會換掉。
_stubs = [n for n in ("torch", "torchaudio") if n not in sys.modules]
for _name in _stubs:
    sys.modules[_name] = types.ModuleType(_name)
try:
    import onnxruntime as ort  # noqa: E402
    from onnx_tts_runtime import OnnxTtsRuntime  # noqa: E402  (MOSS-TTS-Nano repo 根目錄)
finally:
    for _name in _stubs:
        sys.modules.pop(_name, None)

# 合成只用得到這幾個零件；local_decoder、local_cached_step 載了也是白佔記憶體
# （codec_decode_step 平常用不到，但官方 runtime 啟動時一定要拿它，只有 24 MB，留著）
_NEEDED_SESSIONS = ("prefill", "decode", "local_fixed_sampled_frame", "codec_encode", "codec_decode", "codec_decode_step")


class _LeanRuntime(OnnxTtsRuntime):
    """省記憶體版：不用的零件不載，關掉 ONNX Runtime 的記憶體池（用完就還，不然建一次聲線就多佔 2 GB 不放）。"""

    def _session(self, path_value):
        o = ort.SessionOptions()
        o.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_ALL
        o.intra_op_num_threads = self.thread_count
        o.inter_op_num_threads = 1
        o.enable_cpu_mem_arena = False
        o.enable_mem_pattern = False
        return ort.InferenceSession(str(path_value), sess_options=o, providers=self.ort_providers)

    def _create_sessions(self):
        tts_dir, codec_dir = self.tts_meta_path.parent, self.codec_meta_path.parent
        files = {
            "prefill": tts_dir / self.tts_meta["files"]["prefill"],
            "decode": tts_dir / self.tts_meta["files"]["decode_step"],
            "local_fixed_sampled_frame": tts_dir / self.tts_meta["files"]["local_fixed_sampled_frame"],
            "codec_encode": codec_dir / self.codec_meta["files"]["encode"],
            "codec_decode": codec_dir / self.codec_meta["files"]["decode_full"],
            "codec_decode_step": codec_dir / self.codec_meta["files"]["decode_step"],
        }
        return {k: self._session(files[k]) for k in _NEEDED_SESSIONS}

log = logging.getLogger("pocket_voice")

_t2s = OpenCC("t2s")
# 發音修正表：原字=替代字，遇到唸錯的字再加
PRONUNCIATION_FIXES: dict[str, str] = {"妳": "你"}
# 句號、問號、驚嘆號、換行切段；逗號留在段內
_SENTENCE_END = re.compile(r"(?<=[。！？!?；;…])|\n+")
MIN_SEGMENT_CHARS = 6
SEGMENT_PAUSE_SECONDS = 0.35
OUTPUT_SAMPLE_RATE = 24000


def prepare_segments(text: str) -> list[str]:
    """繁轉簡、套發音修正，再切成一段一段；太短的段併到下一段。"""
    s = _t2s.convert(text.strip())
    for src, dst in PRONUNCIATION_FIXES.items():
        s = s.replace(src, dst)
    parts = [p.strip() for p in _SENTENCE_END.split(s) if p and p.strip()]
    segments: list[str] = []
    carry = ""
    for p in parts:
        p = carry + p
        if len(re.sub(r"[\W_]", "", p)) < MIN_SEGMENT_CHARS:
            # 太短：先留著，接到下一段前面（去掉句尾的句號，免得兩段中間停太久）
            carry = p.rstrip("。.") + "，"
            continue
        segments.append(p)
        carry = ""
    if carry:
        tail = carry.rstrip("，")
        if segments:
            segments[-1] = segments[-1] + tail
        else:
            segments.append(tail)
    return segments


def trim_long_silence(data: np.ndarray, sr: int, max_gap: float = 0.6, keep: float = 0.2) -> np.ndarray:
    """參考音裡超過 max_gap 秒的空白縮成 keep 秒（樣本常有開頭、中間的長空白，會拖慢每次合成）。"""
    hop = int(sr * 0.02)
    mono = np.abs(data).mean(axis=1)
    frames = len(mono) // hop
    if not frames:
        return data
    rms = np.sqrt(np.mean(mono[: frames * hop].reshape(frames, hop) ** 2, axis=1))
    quiet = rms < max(0.01, float(np.percentile(rms, 95)) * 0.05)
    keep_mask = np.ones(len(data), dtype=bool)
    run_start = None
    for i, q in enumerate(np.append(quiet, False)):
        if q and run_start is None:
            run_start = i
        elif not q and run_start is not None:
            if (i - run_start) * 0.02 > max_gap:
                cut_from = (run_start * hop) + int(sr * keep / 2)
                cut_to = (i * hop) - int(sr * keep / 2)
                keep_mask[cut_from:cut_to] = False
            run_start = None
    return data[keep_mask]


class PocketVoice:
    def __init__(self, model_dir: str | Path, threads: int = 2) -> None:
        t0 = time.time()
        # output_dir：官方 runtime 啟動時會建這個資料夾，放在可寫的 /tmp（Space 裡其他地方不能寫）
        self.rt = _LeanRuntime(model_dir=str(model_dir), thread_count=threads, output_dir="/tmp/pocket-voice-out")
        self.rt._load_reference_audio = self._load_reference_audio  # 換掉用 torch 的那個
        self.sample_rate = int(self.rt.codec_meta["codec_config"]["sample_rate"])
        self.channels = int(self.rt.codec_meta["codec_config"]["channels"])
        self.lock = threading.Lock()  # ONNX session 不給兩個請求同時用
        self.load_ms = int((time.time() - t0) * 1000)
        log.info("model loaded in %d ms", self.load_ms)

    def _load_reference_audio(self, source) -> np.ndarray:
        data, sr = sf.read(source, dtype="float32", always_2d=True)  # (樣本數, 聲道)
        data = trim_long_silence(data, sr)
        if sr != self.sample_rate:
            g = gcd(sr, self.sample_rate)
            data = resample_poly(data, self.sample_rate // g, sr // g, axis=0).astype(np.float32)
        wav = data.T  # (聲道, 樣本數)
        if wav.shape[0] == 1 and self.channels > 1:
            wav = np.repeat(wav, self.channels, axis=0)
        elif wav.shape[0] > 1 and self.channels == 1:
            wav = wav.mean(axis=0, keepdims=True)
        return wav[np.newaxis].astype(np.float32, copy=False)

    def create_profile(self, audio_bytes: bytes) -> tuple[list[list[int]], float]:
        """參考音 → 聲音代碼。回傳代碼和參考音長度（秒）。"""
        buf = io.BytesIO(audio_bytes)
        info = sf.info(buf)
        seconds = info.frames / info.samplerate
        buf.seek(0)
        with self.lock:
            codes = self.rt.encode_reference_audio(buf)
        return codes, seconds

    def synthesize(self, text: str, codes: list[list[int]], seed: int | None = None) -> tuple[np.ndarray, dict]:
        """回傳單聲道 float32（OUTPUT_SAMPLE_RATE）和耗時。"""
        segments = prepare_segments(text)
        if not segments:
            raise ValueError("empty_text")
        t0 = time.time()
        first_ms = None
        pieces: list[np.ndarray] = []
        pause = np.zeros(int(self.sample_rate * SEGMENT_PAUSE_SECONDS), dtype=np.float32)
        with self.lock:
            if seed is not None:
                self.rt.rng = np.random.default_rng(int(seed))
            for i, seg in enumerate(segments):
                res = self.rt.synthesize_single_chunk(text=seg, prompt_audio_codes=codes, streaming=False)
                wav = np.asarray(res["waveform"], dtype=np.float32)
                wav = wav.mean(axis=1) if wav.ndim == 2 else wav
                if first_ms is None:
                    first_ms = int((time.time() - t0) * 1000)
                if i:
                    pieces.append(pause)
                pieces.append(wav)
        mono = np.concatenate(pieces)
        g = gcd(self.sample_rate, OUTPUT_SAMPLE_RATE)
        mono = resample_poly(mono, OUTPUT_SAMPLE_RATE // g, self.sample_rate // g).astype(np.float32)
        timing = {"load_ms": self.load_ms, "first_audio_ms": first_ms, "total_ms": int((time.time() - t0) * 1000), "segments": len(segments)}
        return mono, timing


def encode_audio(mono: np.ndarray, fmt: str) -> tuple[bytes, str]:
    pcm = np.clip(mono, -1, 1)
    if fmt == "pcm":
        return (pcm * 32767).astype("<i2").tobytes(), "audio/L16; rate=%d; channels=1" % OUTPUT_SAMPLE_RATE
    if fmt == "wav":
        buf = io.BytesIO()
        sf.write(buf, pcm, OUTPUT_SAMPLE_RATE, format="WAV", subtype="PCM_16")
        return buf.getvalue(), "audio/wav"
    import lameenc

    enc = lameenc.Encoder()
    enc.set_bit_rate(96)
    enc.set_in_sample_rate(OUTPUT_SAMPLE_RATE)
    enc.set_channels(1)
    enc.set_quality(2)
    data = enc.encode((pcm * 32767).astype("<i2").tobytes()) + enc.flush()
    return bytes(data), "audio/mpeg"
