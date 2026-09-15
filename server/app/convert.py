"""Media konvertatsiyasi (ffmpeg orqali).

Brauzer MediaRecorder webm formatida yozadi, lekin Telegram:
- ovozli xabar (voice) uchun OGG/Opus
- dumaloq video (video_note) uchun MP4/H.264 (kvadrat)
- oddiy video uchun MP4/H.264
talab qiladi. WebM ni shu formatlarga o'girib yuboramiz, aks holda
Telegram uni "fayl" (document) sifatida yuboradi.
"""
import json
import logging
import subprocess
import tempfile
from pathlib import Path

log = logging.getLogger("chatty.convert")

_FFMPEG_AVAILABLE: bool | None = None


def ffmpeg_available() -> bool:
    global _FFMPEG_AVAILABLE
    if _FFMPEG_AVAILABLE is None:
        try:
            r = subprocess.run(["ffmpeg", "-version"], capture_output=True, timeout=10)
            _FFMPEG_AVAILABLE = r.returncode == 0
        except Exception:  # noqa: BLE001
            _FFMPEG_AVAILABLE = False
    return _FFMPEG_AVAILABLE


def probe(data: bytes, ext: str = ".bin") -> dict | None:
    """ffprobe orqali davomiylik va o'lchamni aniqlaydi.

    Telegram voice note / video note uchun duration va o'lcham shart —
    bo'lmasa fayl oddiy hujjat bo'lib ketadi.
    """
    if not ffmpeg_available() or not data:
        return None
    src = None
    try:
        with tempfile.NamedTemporaryFile(suffix=ext, delete=False) as f:
            f.write(data)
            src = Path(f.name)
        cmd = [
            "ffprobe",
            "-v",
            "error",
            "-show_entries",
            "format=duration",
            "-show_entries",
            "stream=codec_type,width,height",
            "-of",
            "json",
            str(src),
        ]
        proc = subprocess.run(cmd, capture_output=True, timeout=60)
        if proc.returncode != 0:
            return None
        j = json.loads(proc.stdout.decode(errors="ignore") or "{}")
        out: dict = {}
        try:
            out["duration"] = int(float(j.get("format", {}).get("duration") or 0))
        except (TypeError, ValueError):
            out["duration"] = 0
        for st in j.get("streams", []):
            if st.get("codec_type") == "video" and "width" in st:
                out["width"] = int(st.get("width") or 0)
                out["height"] = int(st.get("height") or 0)
            elif st.get("codec_type") == "audio":
                out["has_audio"] = True
        return out
    except Exception as e:  # noqa: BLE001
        log.warning("ffprobe xato: %s", e)
        return None
    finally:
        if src is not None:
            src.unlink(missing_ok=True)


def _convert(src_bytes: bytes, in_ext: str, out_ext: str, args: list[str]) -> bytes | None:
    """ffmpeg yordamida faylni o'giradi va natija bytes qaytaradi."""
    if not ffmpeg_available():
        return None
    src = None
    dst = None
    try:
        with tempfile.NamedTemporaryFile(suffix=in_ext, delete=False) as f:
            f.write(src_bytes)
            src = Path(f.name)
        dst = Path(tempfile.mktemp(suffix=out_ext))
        cmd = ["ffmpeg", "-y", "-nostdin", "-i", str(src), *args, str(dst)]
        proc = subprocess.run(cmd, capture_output=True, timeout=180)
        if proc.returncode != 0:
            log.warning("ffmpeg xato: %s", proc.stderr.decode(errors="ignore")[-300:])
            return None
        return dst.read_bytes()
    except Exception as e:  # noqa: BLE001
        log.warning("Konvertatsiya xato: %s", e)
        return None
    finally:
        if src is not None:
            src.unlink(missing_ok=True)
        if dst is not None:
            dst.unlink(missing_ok=True)


def to_voice_note(data: bytes, ext: str = ".webm") -> bytes | None:
    """Ovozli xabar (OGG/Opus).

    Avval tez remux (qayta kodlamasdan) — deyarli bepul. Ishlamasa, libopus bilan.
    """
    if ext.lower() in {".ogg", ".oga", ".opus"}:
        return data
    # Faqat audio oqimi — video oqimi qo'shilib qolsa Telegram uni video/fayl qabul qiladi
    out = _convert(data, ext, ".ogg", ["-vn", "-map", "0:a:0", "-c:a", "copy"])
    if out:
        return out
    return _convert(data, ext, ".ogg", ["-vn", "-map", "0:a:0", "-c:a", "libopus", "-b:a", "64k"])


def to_video_note(data: bytes, ext: str = ".webm") -> bytes | None:
    """Dumaloq video (MP4/H.264, kvadrat crop, 480x480, maksimum 60 soniya)."""
    return _convert(
        data,
        ext,
        ".mp4",
        [
            "-t", "60",
            "-map", "0:v:0", "-map", "0:a:0?",
            "-vf", "crop='min(iw,ih)':'min(iw,ih)',scale=480:480",
            "-c:v", "libx264", "-preset", "ultrafast", "-crf", "30",
            "-pix_fmt", "yuv420p",
            "-c:a", "aac", "-b:a", "96k",
            "-movflags", "+faststart",
        ],
    )


def to_video(data: bytes, ext: str = ".webm") -> bytes | None:
    """Oddiy video (MP4/H.264, audio saqlanadi). Tez kodlash (ultrafast)."""
    return _convert(
        data,
        ext,
        ".mp4",
        [
            "-map", "0:v:0", "-map", "0:a:0?",
            "-vf", "scale='min(720,iw)':-2",
            "-c:v", "libx264", "-preset", "ultrafast", "-crf", "28",
            "-pix_fmt", "yuv420p",
            "-c:a", "aac", "-b:a", "96k",
            "-movflags", "+faststart",
        ],
    )
