"""Media konvertatsiyasi (ffmpeg orqali).

Brauzer MediaRecorder webm formatida yozadi, lekin Telegram:
- ovozli xabar (voice) uchun OGG/Opus
- dumaloq video (video_note) uchun MP4/H.264 (kvadrat)
- oddiy video uchun MP4/H.264
talab qiladi. WebM ni shu formatlarga o'girib yuboramiz, aks holda
Telegram uni "fayl" (document) sifatida yuboradi.
"""
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
        cmd = ["ffmpeg", "-y", "-i", str(src), *args, str(dst)]
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
    """Ovozli xabar (OGG/Opus). WebM ichidagi Opus'ni remux qilamiz (transcode shart emas)."""
    return _convert(data, ext, ".ogg", ["-c:a", "libopus", "-b:a", "64k"])


def to_video_note(data: bytes, ext: str = ".webm") -> bytes | None:
    """Dumaloq video (MP4/H.264, kvadrat crop, 480x480)."""
    return _convert(
        data,
        ext,
        ".mp4",
        [
            "-vf", "crop='min(iw,ih)':'min(iw,ih)',scale=480:480",
            "-c:v", "libx264", "-preset", "veryfast", "-crf", "30",
            "-pix_fmt", "yuv420p",
            "-c:a", "aac", "-b:a", "96k",
            "-movflags", "+faststart",
        ],
    )


def to_video(data: bytes, ext: str = ".webm") -> bytes | None:
    """Oddiy video (MP4/H.264, audio saqlanadi)."""
    return _convert(
        data,
        ext,
        ".mp4",
        [
            "-c:v", "libx264", "-preset", "veryfast", "-crf", "26",
            "-pix_fmt", "yuv420p",
            "-c:a", "aac", "-b:a", "96k",
            "-movflags", "+faststart",
        ],
    )
