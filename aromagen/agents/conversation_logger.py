from __future__ import annotations

import json
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from .settings import settings

_lock = threading.Lock()


def new_session_id() -> str:
    return str(uuid.uuid4())


def append_event(
    event: str,
    *,
    session_id: Optional[str] = None,
    human_input: Optional[str] = None,
    request: Optional[dict[str, Any]] = None,
    response: Optional[dict[str, Any]] = None,
) -> None:
    """Append one dialogue event to a daily JSONL log file."""
    if not settings.dialogue_logging_enabled:
        return

    record = {
        "session_id": session_id,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "event": event,
        "model": settings.openai_model,
    }
    if human_input is not None:
        record["human_input"] = human_input
    if request is not None:
        record["request"] = request
    if response is not None:
        record["response"] = response

    log_dir = settings.dialogue_log_dir
    log_dir.mkdir(parents=True, exist_ok=True)
    day = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    path = log_dir / f"dialogue_{day}.jsonl"

    line = json.dumps(record, ensure_ascii=False) + "\n"
    with _lock:
        with path.open("a", encoding="utf-8") as f:
            f.write(line)
