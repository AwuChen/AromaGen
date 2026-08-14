"""
Retrieval-augmented context from the production interaction log.

The log (populated by the frontend's "Log" button, POST /log_interaction)
records one row per logged round: {timestamp, target_smell, aromagen_ratio,
similarity, feedback, session_id}. Rows sharing a session_id form one
"block" -- one person's iterative attempt at one target descriptor. For each
block we keep the ratio from whichever round scored the HIGHEST similarity,
that top similarity score, and the full ordered feedback history.

At compose time (initial request only, not feedback rounds -- see
openai_client.compose_with_openai), the user's input is embedded and
compared against every block's target_smell embedding; the top-k most
similar blocks are handed to the model as precedent.

This is additive/best-effort: any failure here (no API key, no log yet,
embedding call failure) degrades to an empty result rather than breaking
composition.
"""
from __future__ import annotations

import json
import logging
import math
import threading
from typing import Any, Dict, List, Optional

from openai import OpenAI

from .settings import settings

log = logging.getLogger(__name__)

_log_write_lock = threading.Lock()
_embedding_cache_lock = threading.Lock()


def append_local_log(record: Dict[str, Any]) -> None:
    """Append one row to the local JSONL log. Best-effort: a failure here is
    logged, not raised, so it can never take down the /log_interaction
    request that also writes to the Apps Script sheet."""
    try:
        path = settings.interaction_log_local_path
        path.parent.mkdir(parents=True, exist_ok=True)
        with _log_write_lock:
            with path.open("a", encoding="utf-8") as f:
                f.write(json.dumps(record, ensure_ascii=False) + "\n")
    except Exception as e:
        log.warning("Failed to append to local interaction log: %s", e)


def _load_rows() -> List[Dict[str, Any]]:
    path = settings.interaction_log_local_path
    if not path.exists():
        return []
    rows: List[Dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return rows


def _group_into_blocks(rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Group rows by session_id, in first-seen order. Rows without a
    session_id each form their own single-row block (never merged together)."""
    blocks: "Dict[str, Dict[str, Any]]" = {}
    order: List[str] = []
    for i, row in enumerate(rows):
        session_id = row.get("session_id") or f"__no_session_{i}__"
        target_smell = (row.get("target_smell") or "").strip()
        if not target_smell:
            continue
        if session_id not in blocks:
            blocks[session_id] = {
                "session_id": session_id,
                "target_smell": target_smell,
                "best_ratio": row.get("aromagen_ratio", ""),
                "best_similarity": None,
                "feedback_history": [],
            }
            order.append(session_id)
        block = blocks[session_id]
        similarity = row.get("similarity")
        if isinstance(similarity, (int, float)) and (
            block["best_similarity"] is None or similarity > block["best_similarity"]
        ):
            block["best_similarity"] = similarity
            block["best_ratio"] = row.get("aromagen_ratio", block["best_ratio"])
        feedback = (row.get("feedback") or "").strip()
        if feedback:
            block["feedback_history"].append(feedback)
    return [blocks[sid] for sid in order]


def _load_embedding_cache() -> Dict[str, List[float]]:
    path = settings.interaction_log_embeddings_path
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except (json.JSONDecodeError, OSError):
        return {}


def _save_embedding_cache(cache: Dict[str, List[float]]) -> None:
    path = settings.interaction_log_embeddings_path
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(cache, ensure_ascii=False), encoding="utf-8")


def _cosine_similarity(a: List[float], b: List[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(y * y for y in b))
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)


def _get_embeddings(texts: List[str], client: OpenAI) -> Dict[str, List[float]]:
    """Return {text: embedding}, using a persistent on-disk cache so only
    genuinely new target descriptors (or the current query) cost an API call."""
    unique_texts = list(dict.fromkeys(t for t in texts if t))
    with _embedding_cache_lock:
        cache = _load_embedding_cache()
    missing = [t for t in unique_texts if t not in cache]
    if missing:
        response = client.embeddings.create(model=settings.interaction_retrieval_embedding_model, input=missing)
        for text, item in zip(missing, response.data):
            cache[text] = item.embedding
        with _embedding_cache_lock:
            # Re-load + merge rather than blind overwrite, in case another
            # request updated the cache concurrently in between.
            latest = _load_embedding_cache()
            latest.update(cache)
            _save_embedding_cache(latest)
            cache = latest
    return {t: cache[t] for t in unique_texts if t in cache}


def get_top_k_blocks(user_input: str, k: Optional[int] = None) -> List[Dict[str, Any]]:
    """Top-k past session blocks whose target_smell is semantically closest
    to user_input, each with the ratio/feedback/rating that mattered most
    (highest-scoring round). Returns [] on any failure or if disabled/empty."""
    if not settings.interaction_retrieval_enabled or not settings.openai_api_key:
        return []
    top_k = k if k is not None else settings.interaction_retrieval_top_k

    try:
        rows = _load_rows()
        if not rows:
            return []
        blocks = _group_into_blocks(rows)
        if not blocks:
            return []

        client = OpenAI(api_key=settings.openai_api_key)
        unique_targets = list(dict.fromkeys(b["target_smell"] for b in blocks))
        embeddings = _get_embeddings(unique_targets + [user_input], client)

        query_vec = embeddings.get(user_input)
        if query_vec is None:
            return []

        scored = []
        for block in blocks:
            target_vec = embeddings.get(block["target_smell"])
            if target_vec is None:
                continue
            scored.append((_cosine_similarity(query_vec, target_vec), block))

        scored.sort(key=lambda pair: pair[0], reverse=True)
        return [
            {
                "target_smell": block["target_smell"],
                "best_ratio": block["best_ratio"],
                "best_similarity": block["best_similarity"],
                "feedback_history": block["feedback_history"],
                "similarity_to_current_request": round(score, 4),
            }
            for score, block in scored[:top_k]
        ]
    except Exception as e:
        log.warning("Interaction-log retrieval failed (%s); composing without precedent", e)
        return []
