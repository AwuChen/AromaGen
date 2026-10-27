from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

from .schemas import ScentItem


def _ratio_map(sequence: Sequence[ScentItem]) -> Dict[str, float]:
    totals: Dict[str, float] = {}
    for item in sequence:
        totals[item.scent_name] = totals.get(item.scent_name, 0.0) + max(float(item.ratio), 0.0)
    if not totals:
        return {}
    total = sum(totals.values())
    if total <= 0:
        n = len(totals)
        return {name: 1.0 / n for name in totals}
    return {name: value / total for name, value in totals.items()}


def sequence_to_vector(sequence: Sequence[ScentItem], odorant_names: Iterable[str]) -> Dict[str, float]:
    """Normalized 12-channel (or catalog-sized) ratio vector."""
    base = {name: 0.0 for name in odorant_names}
    ratios = _ratio_map(sequence)
    for name, value in ratios.items():
        if name in base:
            base[name] = value
    total = sum(base.values())
    if total <= 0:
        return base
    return {name: value / total for name, value in base.items()}


def blend_vectors(
    a: Dict[str, float],
    b: Dict[str, float],
    c: Dict[str, float],
    weights: Tuple[float, float, float],
) -> Dict[str, float]:
    w1, w2, w3 = weights
    s = w1 + w2 + w3
    if s <= 0:
        raise ValueError("Barycentric weights must sum to a positive value")
    w1, w2, w3 = w1 / s, w2 / s, w3 / s
    keys = set(a) | set(b) | set(c)
    blended = {key: w1 * a.get(key, 0.0) + w2 * b.get(key, 0.0) + w3 * c.get(key, 0.0) for key in keys}
    total = sum(blended.values())
    if total <= 0:
        raise ValueError("Blend produced zero mass; check anchor recipes")
    return {key: value / total for key, value in blended.items()}


def vector_to_sequence(
    vector: Dict[str, float],
    *,
    pulse_seconds: float,
    min_ratio: float = 0.02,
) -> List[ScentItem]:
    """Drop negligible channels and return catalog-valid ScentItems."""
    items = [
        (name, ratio)
        for name, ratio in vector.items()
        if ratio >= min_ratio
    ]
    items.sort(key=lambda pair: pair[1], reverse=True)
    if not items:
        raise ValueError("No odorants above minimum ratio after blending")
    return [
        ScentItem(scent_name=name, scent_duration=pulse_seconds, ratio=ratio)
        for name, ratio in items
    ]


def barycentric_from_point(
    px: float,
    py: float,
    ax: float,
    ay: float,
    bx: float,
    by: float,
    cx: float,
    cy: float,
) -> Tuple[float, float, float]:
    """Return (w_a, w_b, w_c) for vertices A, B, C. Clamps negative weights to 0 and renormalizes."""
    v0x, v0y = cx - ax, cy - ay
    v1x, v1y = bx - ax, by - ay
    v2x, v2y = px - ax, py - ay
    dot00 = v0x * v0x + v0y * v0y
    dot01 = v0x * v1x + v0y * v1y
    dot11 = v1x * v1x + v1y * v1y
    dot20 = v2x * v0x + v2y * v0y
    dot21 = v2x * v1x + v2y * v1y
    denom = dot00 * dot11 - dot01 * dot01
    if abs(denom) < 1e-12:
        return (1.0 / 3.0, 1.0 / 3.0, 1.0 / 3.0)
    # p = A + w*(B - A) + v*(C - A)  =>  p = u*A + w*B + v*C,  u = 1 - w - v
    coeff_c = (dot11 * dot20 - dot01 * dot21) / denom
    coeff_b = (dot00 * dot21 - dot01 * dot20) / denom
    coeff_a = 1.0 - coeff_c - coeff_b
    w_a, w_b, w_c = max(coeff_a, 0.0), max(coeff_b, 0.0), max(coeff_c, 0.0)
    total = w_a + w_b + w_c
    if total <= 0:
        return (1.0 / 3.0, 1.0 / 3.0, 1.0 / 3.0)
    return (w_a / total, w_b / total, w_c / total)


def point_from_barycentric(
    weights: Tuple[float, float, float],
    ax: float,
    ay: float,
    bx: float,
    by: float,
    cx: float,
    cy: float,
) -> Tuple[float, float]:
    w1, w2, w3 = weights
    s = w1 + w2 + w3
    if s <= 0:
        w1 = w2 = w3 = 1.0 / 3.0
    else:
        w1, w2, w3 = w1 / s, w2 / s, w3 / s
    px = w1 * ax + w2 * bx + w3 * cx
    py = w1 * ay + w2 * by + w3 * cy
    return px, py


def l2_distance(a: Dict[str, float], b: Dict[str, float]) -> float:
    keys = set(a) | set(b)
    return math.sqrt(sum((a.get(k, 0.0) - b.get(k, 0.0)) ** 2 for k in keys))


def load_corpus_vectors(examples_path: Path, odorant_names: List[str]) -> List[Tuple[str, Dict[str, float], List[ScentItem]]]:
    if not examples_path.exists():
        return []
    with examples_path.open("r", encoding="utf-8") as f:
        raw = json.load(f)
    if not isinstance(raw, list):
        return []
    out: List[Tuple[str, Dict[str, float], List[ScentItem]]] = []
    for entry in raw:
        sentence = str(entry.get("sentence") or entry.get("id") or "")
        seq_raw = entry.get("scent_sequence") or []
        sequence: List[ScentItem] = []
        for item in seq_raw:
            if not isinstance(item, dict):
                continue
            name = item.get("scent_name")
            if not name:
                continue
            duration = float(item.get("scent_duration") or 1.0)
            ratio = float(item.get("ratio") or 1.0)
            sequence.append(ScentItem(scent_name=name, scent_duration=duration, ratio=ratio))
        if not sequence:
            continue
        vector = sequence_to_vector(sequence, odorant_names)
        out.append((sentence, vector, sequence))
    return out


def nearest_corpus_recipe(
    target: Dict[str, float],
    corpus: List[Tuple[str, Dict[str, float], List[ScentItem]]],
) -> Optional[Dict[str, Any]]:
    if not corpus:
        return None
    best: Optional[Tuple[float, str, List[ScentItem]]] = None
    for sentence, vector, sequence in corpus:
        dist = l2_distance(target, vector)
        if best is None or dist < best[0]:
            best = (dist, sentence, sequence)
    if best is None:
        return None
    dist, sentence, sequence = best
    return {"distance": dist, "sentence": sentence, "scent_sequence": sequence}


DEFAULT_ANCHOR_PRESETS: List[Dict[str, Any]] = [
    {
        "token": "A",
        "label": "Token A · floral",
        "scent_sequence": [
            {"scent_name": "Lavender + Rose", "ratio": 0.55, "scent_duration": 1.0},
            {"scent_name": "Benz Sal", "ratio": 0.25, "scent_duration": 1.0},
            {"scent_name": "Orange + Lemon", "ratio": 0.20, "scent_duration": 1.0},
        ],
    },
    {
        "token": "B",
        "label": "Token B · gourmand",
        "scent_sequence": [
            {"scent_name": "Vanilla Sugar + Almond Extract", "ratio": 0.50, "scent_duration": 1.0},
            {"scent_name": "Cognac", "ratio": 0.30, "scent_duration": 1.0},
            {"scent_name": "Benz Sal", "ratio": 0.20, "scent_duration": 1.0},
        ],
    },
    {
        "token": "C",
        "label": "Token C · woody",
        "scent_sequence": [
            {"scent_name": "Sandalwood", "ratio": 0.45, "scent_duration": 1.0},
            {"scent_name": "Birch tar oil + Coffee + Clove Bud", "ratio": 0.35, "scent_duration": 1.0},
            {"scent_name": "Clove Bud + Cumin", "ratio": 0.20, "scent_duration": 1.0},
        ],
    },
]
