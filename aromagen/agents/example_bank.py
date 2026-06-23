from __future__ import annotations

import json
import re
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from .schemas import FeedbackRound, ScentItem
from .settings import settings

_lock = threading.Lock()
_MAX_EXAMPLES = 100

_TOKEN_RE = re.compile(r"[^\w]+", re.UNICODE)


def _tokenize(text: str) -> set[str]:
    lowered = text.lower()
    parts = _TOKEN_RE.split(lowered)
    return {p for p in parts if p}


def _similarity_score(query: str, example_sentence: str) -> float:
    query_tokens = _tokenize(query)
    if not query_tokens:
        return 0.0
    example_tokens = _tokenize(example_sentence)
    if not example_tokens:
        return 0.0
    overlap = len(query_tokens & example_tokens)
    return overlap / len(query_tokens)


def _ensure_file(path: Path) -> None:
    if not path.exists():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("[]\n", encoding="utf-8")


def _load_examples_unlocked(path: Path) -> List[Dict[str, Any]]:
    _ensure_file(path)
    raw = path.read_text(encoding="utf-8")
    data = json.loads(raw or "[]")
    if not isinstance(data, list):
        return []
    return data


def load_examples() -> List[Dict[str, Any]]:
    path = settings.learned_examples_path
    with _lock:
        return _load_examples_unlocked(path)


def _save_examples(examples: List[Dict[str, Any]]) -> None:
    path = settings.learned_examples_path
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(examples, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _build_feedback_summary(rounds: List[FeedbackRound]) -> List[str]:
    summary: List[str] = []
    for round_item in rounds:
        summary.append(f"{round_item.feedback_text} → {round_item.changes_made}")
    return summary


def add_example(
    *,
    sentence: str,
    scent_sequence: List[ScentItem],
    feedback_rounds: List[FeedbackRound] = [],
    rating: Optional[int] = None,
) -> Dict[str, Any]:
    record: Dict[str, Any] = {
        "id": str(uuid.uuid4()),
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "sentence": sentence,
        "scent_sequence": [
            {"scent_name": item.scent_name, "scent_duration": item.scent_duration}
            for item in scent_sequence
        ],
        "feedback_summary": _build_feedback_summary(feedback_rounds),
        "rounds": len(feedback_rounds),
    }
    if rating is not None:
        record["rating"] = rating

    with _lock:
        path = settings.learned_examples_path
        examples = _load_examples_unlocked(path)
        examples.append(record)
        if len(examples) > _MAX_EXAMPLES:
            examples = examples[-_MAX_EXAMPLES:]
        _save_examples(examples)

    return record


def find_similar(sentence: str, k: Optional[int] = None) -> List[Dict[str, Any]]:
    if not settings.learned_examples_enabled:
        return []

    top_k = k if k is not None else settings.learned_examples_top_k
    examples = load_examples()
    if not examples:
        return []

    scored = [
        (_similarity_score(sentence, ex.get("sentence", "")), ex)
        for ex in examples
    ]
    scored = [pair for pair in scored if pair[0] > 0]
    if not scored:
        return []

    scored.sort(key=lambda pair: pair[0], reverse=True)
    return [ex for _, ex in scored[:top_k]]
