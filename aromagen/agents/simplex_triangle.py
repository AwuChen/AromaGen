from __future__ import annotations

import logging
import re
from typing import Any, Dict, List, Literal, Optional, Tuple

from .cartridge import validate_composition
from .descriptor_filter import filter_relevant_scents
from .example_bank import find_similar
from .interaction_retrieval import (
    find_exact_session_block,
    get_top_k_blocks,
    parse_ratio_string,
)
from .openai_client import compose_with_openai, expand_to_pulse_sequence, plan_triangle_directions
from .schemas import ScentItem
from .settings import settings
from .simplex import (
    DEFAULT_ANCHOR_PRESETS,
    l2_distance,
    sequence_to_vector,
    vector_to_sequence,
)

log = logging.getLogger(__name__)

CORNER_ALPHAS = (0.35, 0.45, 0.55, 0.65)
CornerMode = Literal["preset", "cluster", "llm"]

_TOKEN_RE = re.compile(r"[^\w]+", re.UNICODE)


def _tokenize(text: str) -> set[str]:
    return {p for p in _TOKEN_RE.split((text or "").lower()) if p}


def _dicts_to_items(raw: List[Dict[str, Any]]) -> List[ScentItem]:
    return [ScentItem(**entry) for entry in raw]


def _summarize_sequence(sequence: List[ScentItem]) -> str:
    total = sum(item.ratio for item in sequence)
    if total <= 0:
        return ", ".join(item.scent_name for item in sequence)
    return ", ".join(
        f"{item.scent_name} {round((item.ratio / total) * 100)}%" for item in sequence
    )


def _mix_vectors(
    center: Dict[str, float],
    direction: Dict[str, float],
    alpha: float,
) -> Dict[str, float]:
    keys = set(center) | set(direction)
    blended = {
        key: (1.0 - alpha) * center.get(key, 0.0) + alpha * direction.get(key, 0.0) for key in keys
    }
    total = sum(blended.values())
    if total <= 0:
        return dict(center)
    return {key: value / total for key, value in blended.items()}


def _min_pairwise_l2(vectors: List[Dict[str, float]]) -> float:
    if len(vectors) < 2:
        return 0.0
    best = float("inf")
    for i in range(len(vectors)):
        for j in range(i + 1, len(vectors)):
            best = min(best, l2_distance(vectors[i], vectors[j]))
    return best if best != float("inf") else 0.0


def _build_corners_from_directions(
    center_vec: Dict[str, float],
    directions: List[Tuple[str, Dict[str, float]]],
    pulse_seconds: float,
) -> Tuple[List[ScentItem], List[ScentItem], List[ScentItem], float, float]:
    if len(directions) < 3:
        raise ValueError("Need at least three direction vectors for corners")

    direction_vectors = [d[1] for d in directions[:3]]

    best_alpha = CORNER_ALPHAS[0]
    best_score = -1.0
    best_corners: Optional[List[Dict[str, float]]] = None
    for alpha in CORNER_ALPHAS:
        corners = [_mix_vectors(center_vec, dv, alpha) for dv in direction_vectors]
        score = _min_pairwise_l2(corners)
        if score > best_score:
            best_score = score
            best_alpha = alpha
            best_corners = corners

    assert best_corners is not None
    sequences = [vector_to_sequence(vec, pulse_seconds=pulse_seconds) for vec in best_corners]
    return sequences[0], sequences[1], sequences[2], best_alpha, best_score


def _preset_directions(odorant_names: List[str]) -> List[Tuple[str, Dict[str, float]]]:
    out: List[Tuple[str, Dict[str, float]]] = []
    for preset in DEFAULT_ANCHOR_PRESETS:
        raw = preset.get("label") or preset["token"]
        semantic = raw.split("·")[-1].strip() if "·" in raw else raw
        seq = _dicts_to_items(preset["scent_sequence"])
        out.append((semantic, sequence_to_vector(seq, odorant_names)))
    return out


def _score_category_for_target(category: str, names: List[str], catalog: Dict[str, Any], target: str) -> int:
    tokens = _tokenize(target)
    score = len(tokens & _tokenize(category))
    for name in names:
        score += len(tokens & _tokenize(name))
        score += len(tokens & _tokenize(catalog.get(name, {}).get("note", "")))
    return score


def _category_unit_vector(
    names: List[str],
    catalog: Dict[str, Any],
    target: str,
    odorant_names: List[str],
) -> Dict[str, float]:
    tokens = _tokenize(target)
    best_name = names[0]
    best = -1
    for name in names:
        s = len(tokens & _tokenize(name)) + len(tokens & _tokenize(catalog.get(name, {}).get("note", "")))
        if s > best:
            best = s
            best_name = name
    vec = {n: 0.0 for n in odorant_names}
    vec[best_name] = 1.0
    return vec


def _select_three_spread(
    candidates: List[Tuple[str, Dict[str, float]]],
) -> List[Tuple[str, Dict[str, float]]]:
    if len(candidates) <= 3:
        return candidates
    chosen: List[Tuple[str, Dict[str, float]]] = [candidates[0]]
    pool = candidates[1:]
    while len(chosen) < 3 and pool:
        best_item = pool[0]
        best_score = -1.0
        for item in pool:
            vecs = [c[1] for c in chosen] + [item[1]]
            score = _min_pairwise_l2(vecs)
            if score > best_score:
                best_score = score
                best_item = item
        chosen.append(best_item)
        pool = [p for p in pool if p is not best_item]
    while len(chosen) < 3:
        chosen.append(candidates[len(chosen) % len(candidates)])
    return chosen[:3]


def _cluster_directions(
    target: str,
    catalog: Dict[str, Dict[str, Any]],
    odorant_names: List[str],
) -> List[Tuple[str, Dict[str, float]]]:
    by_category: Dict[str, List[str]] = {}
    for name, meta in catalog.items():
        cat = (meta.get("category") or "Other").strip()
        by_category.setdefault(cat, []).append(name)

    scored: List[Tuple[int, str, List[str]]] = []
    for cat, names in by_category.items():
        scored.append((_score_category_for_target(cat, names, catalog, target), cat, names))
    scored.sort(key=lambda t: t[0], reverse=True)

    candidates: List[Tuple[str, Dict[str, float]]] = []
    for _score, cat, names in scored:
        vec = _category_unit_vector(names, catalog, target, odorant_names)
        candidates.append((cat, vec))

    if not candidates:
        return _preset_directions(odorant_names)

    selected = _select_three_spread(candidates)
    return selected


def _llm_directions(
    target: str,
    center_sequence: List[ScentItem],
    catalog: Dict[str, Dict[str, Any]],
    cartridge_status: Dict[str, Any],
    odorant_names: List[str],
) -> List[Tuple[str, Dict[str, float]]]:
    summary = _summarize_sequence(center_sequence)
    plan = plan_triangle_directions(target, summary)
    directions: List[Tuple[str, Dict[str, float]]] = []
    for item in plan.directions[:3]:
        label = item.short_label.strip()
        sentence = (
            f"{target} — center reference mix: {summary}. "
            f"Navigation corner; emphasize {item.facet.strip()}. "
            "Distinct from the center and from the other corners."
        )
        narrowed = filter_relevant_scents(sentence, catalog, settings.descriptor_filter_top_k)
        result = compose_with_openai(sentence, narrowed, cartridge_status)
        validate_composition(result.scent_sequence, catalog)
        vec = sequence_to_vector(result.scent_sequence, odorant_names)
        directions.append((label, vec))
    return directions


def resolve_center_sequence(
    target: str,
    catalog: Dict[str, Dict[str, Any]],
    cartridge_status: Dict[str, Any],
) -> Tuple[List[ScentItem], str, Dict[str, Any]]:
    """Return (scent_sequence, source_tag, metadata)."""
    pulse = settings.pulse_seconds
    meta: Dict[str, Any] = {"target": target.strip()}

    exact = find_exact_session_block(target)
    if exact and exact.get("best_ratio"):
        parsed = parse_ratio_string(exact["best_ratio"], pulse_seconds=pulse)
        if parsed:
            sequence = _dicts_to_items(parsed)
            validate_composition(sequence, catalog)
            meta.update(
                {
                    "matched_target": exact.get("target_smell"),
                    "best_similarity": exact.get("best_similarity"),
                    "session_id": exact.get("session_id"),
                }
            )
            return sequence, "exact_log", meta

    neighbors = get_top_k_blocks(target, k=15)
    rated = [b for b in neighbors if b.get("best_ratio") and b.get("best_similarity") is not None]
    if rated:
        rated.sort(
            key=lambda b: (
                float(b.get("best_similarity") or 0),
                float(b.get("similarity_to_current_request") or 0),
            ),
            reverse=True,
        )
        best = rated[0]
        parsed = parse_ratio_string(best.get("best_ratio", ""), pulse_seconds=pulse)
        if parsed:
            sequence = _dicts_to_items(parsed)
            validate_composition(sequence, catalog)
            meta.update(
                {
                    "matched_target": best.get("target_smell"),
                    "best_similarity": best.get("best_similarity"),
                    "similarity_to_current_request": best.get("similarity_to_current_request"),
                }
            )
            return sequence, "retrieved_log", meta

    if neighbors:
        for block in neighbors:
            parsed = parse_ratio_string(block.get("best_ratio", ""), pulse_seconds=pulse)
            if not parsed:
                continue
            sequence = _dicts_to_items(parsed)
            try:
                validate_composition(sequence, catalog)
            except ValueError:
                continue
            meta.update(
                {
                    "matched_target": block.get("target_smell"),
                    "best_similarity": block.get("best_similarity"),
                    "similarity_to_current_request": block.get("similarity_to_current_request"),
                }
            )
            return sequence, "retrieved_log_nearest", meta

    for ex in find_similar(target, k=5):
        raw_seq = ex.get("scent_sequence") or []
        if not raw_seq:
            continue
        sequence = []
        for item in raw_seq:
            if not isinstance(item, dict) or not item.get("scent_name"):
                continue
            sequence.append(
                ScentItem(
                    scent_name=item["scent_name"],
                    scent_duration=float(item.get("scent_duration") or pulse),
                    ratio=float(item.get("ratio") or 1.0),
                )
            )
        if not sequence:
            continue
        try:
            validate_composition(sequence, catalog)
        except ValueError:
            continue
        meta.update({"matched_target": ex.get("sentence"), "example_id": ex.get("id")})
        return sequence, "learned_example", meta

    log.info("No retrieval hit for %r; composing center with RAG", target)
    narrowed = filter_relevant_scents(target, catalog, settings.descriptor_filter_top_k)
    composed = compose_with_openai(target, narrowed, cartridge_status)
    validate_composition(composed.scent_sequence, catalog)
    meta["justification"] = composed.justification
    return composed.scent_sequence, "composed_rag", meta


def _anchor_label(token: str, semantic: str, neutral_labels: bool) -> str:
    if neutral_labels:
        return f"Token {token}"
    return f"Token {token} · {semantic}"


def prepare_triangle(
    target: str,
    catalog: Dict[str, Dict[str, Any]],
    cartridge_status: Dict[str, Any],
    *,
    corner_mode: CornerMode = "preset",
    neutral_labels: bool = False,
) -> Dict[str, Any]:
    center_sequence, center_source, center_meta = resolve_center_sequence(
        target, catalog, cartridge_status
    )
    odorant_names = list(catalog.keys())
    center_vec = sequence_to_vector(center_sequence, odorant_names)

    if corner_mode == "cluster":
        direction_specs = _cluster_directions(target, catalog, odorant_names)
    elif corner_mode == "llm":
        direction_specs = _llm_directions(
            target, center_sequence, catalog, cartridge_status, odorant_names
        )
    else:
        direction_specs = _preset_directions(odorant_names)

    seq_a, seq_b, seq_c, alpha, spread_score = _build_corners_from_directions(
        center_vec, direction_specs, settings.pulse_seconds
    )

    center_pulse = expand_to_pulse_sequence(
        center_sequence, settings.pulse_seconds, settings.pulse_rounds
    )
    tokens = ("A", "B", "C")
    sequences = (seq_a, seq_b, seq_c)
    anchors_out: List[Dict[str, Any]] = []
    for token, (semantic, _vec), seq in zip(tokens, direction_specs[:3], sequences):
        label = _anchor_label(token, semantic, neutral_labels)
        validate_composition(seq, catalog)
        pulse = expand_to_pulse_sequence(seq, settings.pulse_seconds, settings.pulse_rounds)
        anchors_out.append(
            {
                "token": token,
                "label": label,
                "direction_hint": semantic,
                "scent_sequence": [item.model_dump() for item in seq],
                "pulse_sequence": [item.model_dump() for item in pulse],
            }
        )

    return {
        "target": target.strip(),
        "corner_mode": corner_mode,
        "neutral_labels": neutral_labels,
        "center": {
            "scent_sequence": [item.model_dump() for item in center_sequence],
            "pulse_sequence": [item.model_dump() for item in center_pulse],
            "source": center_source,
            "metadata": center_meta,
        },
        "anchors": anchors_out,
        "corner_alpha": alpha,
        "corner_min_pairwise_l2": round(spread_score, 4),
    }
