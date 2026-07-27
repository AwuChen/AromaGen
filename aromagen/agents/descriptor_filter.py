from __future__ import annotations

import hashlib
import re
from typing import Any, Dict

_TOKEN_RE = re.compile(r"[^\w]+", re.UNICODE)


def _tokenize(text: str) -> set[str]:
    return {p for p in _TOKEN_RE.split(text.lower()) if p}


def _tie_break_key(request_text: str, odorant_name: str) -> str:
    """Deterministic but request-dependent, so zero-overlap ties don't always
    favor the same fixed subset of odorants."""
    return hashlib.sha256(f"{request_text}|{odorant_name}".encode("utf-8")).hexdigest()


def filter_relevant_scents(
    request_text: str,
    catalog: Dict[str, Dict[str, Any]],
    top_k: int,
) -> Dict[str, Dict[str, Any]]:
    """Narrow the full odorant catalog to the top_k entries most relevant to
    request_text, ranked by word overlap against each odorant's category/note.

    Always returns exactly min(top_k, len(catalog)) entries -- never fewer --
    so a request with little literal overlap against any odorant still gets a
    usable catalog instead of an empty one.
    """
    if top_k >= len(catalog):
        return dict(catalog)

    request_tokens = _tokenize(request_text)

    scored = []
    for name, meta in catalog.items():
        descriptor_text = f"{meta.get('category', '')} {meta.get('note', '')}"
        overlap = len(request_tokens & _tokenize(descriptor_text))
        scored.append((overlap, _tie_break_key(request_text, name), name))

    scored.sort(key=lambda item: (-item[0], item[1]))
    selected_names = [name for _, _, name in scored[:top_k]]
    return {name: catalog[name] for name in selected_names}
