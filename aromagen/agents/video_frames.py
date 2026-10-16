"""Extract still frames from short video clips for vision → compose."""
from __future__ import annotations

import logging
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import List, Optional, Set, Tuple

log = logging.getLogger(__name__)

# Fallback sample times (seconds) when duration cannot be read.
_FALLBACK_TIMES_SEC = ("0.5", "1.0", "2.0", "0.25")


def ffmpeg_available() -> bool:
    return shutil.which("ffmpeg") is not None


def _probe_duration_sec(path: Path) -> Optional[float]:
    ffprobe = shutil.which("ffprobe")
    if not ffprobe:
        return None
    proc = subprocess.run(
        [
            ffprobe,
            "-v",
            "error",
            "-show_entries",
            "format=duration",
            "-of",
            "default=noprint_wrappers=1:nokey=1",
            str(path),
        ],
        capture_output=True,
        text=True,
    )
    if proc.returncode != 0:
        return None
    try:
        value = float((proc.stdout or "").strip())
    except ValueError:
        return None
    if value <= 0 or value != value:  # NaN
        return None
    return value


def _mid_sample_times_sec(duration: Optional[float]) -> List[str]:
    if duration is None or duration <= 0.2:
        return list(_FALLBACK_TIMES_SEC)
    mid = duration / 2.0
    lo = 0.05
    hi = max(lo, duration - 0.05)
    candidates = [
        mid,
        max(lo, mid - 0.033),
        min(hi, mid + 0.033),
        max(lo, mid - 0.1),
        min(hi, mid + 0.1),
    ]
    seen: Set[str] = set()
    ordered: List[str] = []
    for t in candidates:
        key = f"{t:.3f}"
        if key in seen:
            continue
        seen.add(key)
        ordered.append(key)
    return ordered


def extract_mid_video_frame(video_bytes: bytes, filename: str) -> Tuple[bytes, str, float]:
    """
    Return (jpeg_bytes, content_type, sample_time_sec) from a frame near the
    middle of the clip (with small seek fallbacks if that frame is unreadable).
    """
    if not ffmpeg_available():
        raise RuntimeError(
            "ffmpeg is not installed or not on PATH. "
            "Install ffmpeg for server-side video, or use the demo UI (browser frame capture)."
        )

    suffix = Path(filename or "clip.mp4").suffix or ".mp4"
    if suffix.lower() not in {".mp4", ".webm", ".mov", ".mkv", ".m4v"}:
        suffix = ".mp4"

    with tempfile.TemporaryDirectory(prefix="aromagen_vid_") as tmp:
        inp = Path(tmp) / f"input{suffix}"
        out = Path(tmp) / "frame.jpg"
        inp.write_bytes(video_bytes)

        duration = _probe_duration_sec(inp)
        sample_times = _mid_sample_times_sec(duration)

        last_err = ""
        for ss in sample_times:
            out.unlink(missing_ok=True)
            proc = subprocess.run(
                [
                    "ffmpeg",
                    "-y",
                    "-ss",
                    ss,
                    "-i",
                    str(inp),
                    "-frames:v",
                    "1",
                    "-q:v",
                    "2",
                    str(out),
                ],
                capture_output=True,
                text=True,
            )
            if proc.returncode != 0:
                last_err = (proc.stderr or proc.stdout or "")[-500:]
                continue
            if out.is_file() and out.stat().st_size > 400:
                return out.read_bytes(), "image/jpeg", float(ss)

        raise RuntimeError(f"Could not extract a frame from video. ffmpeg: {last_err}")


def extract_early_video_frame(video_bytes: bytes, filename: str) -> Tuple[bytes, str, float]:
    """Backward-compatible alias — now samples the middle of the clip."""
    return extract_mid_video_frame(video_bytes, filename)
