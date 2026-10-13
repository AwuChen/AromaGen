"""
Retrieve the best-known composition from RAG stores (interaction log + learned
examples) and use it directly when similarity is strong enough; otherwise fall
back to LLM compose / ensemble.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

from openai import OpenAI

from .example_bank import load_examples
from .interaction_retrieval import get_top_k_blocks, parse_aromagen_ratio
from .schemas import ComposeResponse, ScentItem
from .settings import settings

log = logging.getLogger(__name__)


@dataclass
class RagHit:
    source: str
    matched_text: str
    embedding_similarity: float
    rank_score: float
    scent_sequence: List[ScentItem]
    best_similarity: Optional[float] = None
    accept_rating: Optional[int] = None
    example_id: Optional[str] = None


def _quality_score(hit: RagHit) -> float:
    """Interaction-log similarity is 1–7; learned-example accept ratings are 1–5."""
    if hit.best_similarity is not None:
        return float(hit.best_similarity)
    if hit.accept_rating is not None:
        return float(hit.accept_rating) * 7.0 / 5.0
    return 0.0


def _ratio_string_to_sequence(ratio_str: str, catalog: Dict[str, Any]) -> List[ScentItem]:
    pairs = parse_aromagen_ratio(ratio_str)
    if not pairs:
        return []
    total_pct = sum(pct for _, pct in pairs) or 100.0
    items: List[ScentItem] = []
    for name, pct in pairs:
        if name not in catalog:
            return []
        ratio = pct / total_pct
        duration = min(
            float(settings.scent_duration_max),
            max(1.0, ratio * float(settings.sequence_total_seconds)),
        )
        items.append(ScentItem(scent_name=name, scent_duration=duration, ratio=ratio))
    return items


def _learned_example_to_sequence(example: Dict[str, Any], catalog: Dict[str, Any]) -> List[ScentItem]:
    raw = example.get("scent_sequence") or []
    if not raw:
        return []
    names: List[str] = []
    for entry in raw:
        name = entry.get("scent_name")
        if not name or name not in catalog:
            return []
        names.append(name)
    n = len(names)
    share = 1.0 / n
    items: List[ScentItem] = []
    for entry in raw:
        name = entry["scent_name"]
        duration = float(entry.get("scent_duration") or settings.sequence_total_seconds / n)
        duration = min(float(settings.scent_duration_max), max(1.0, duration))
        items.append(ScentItem(scent_name=name, scent_duration=duration, ratio=share))
    return items


def _embedding_similarity_map(query: str, texts: List[str]) -> Dict[str, float]:
    if not texts or not settings.openai_api_key:
        return {}
    from .interaction_retrieval import _get_embeddings  # reuse disk cache

    client = OpenAI(api_key=settings.openai_api_key)
    unique = list(dict.fromkeys(t for t in texts if t))
    embeddings = _get_embeddings(unique + [query], client)
    query_vec = embeddings.get(query)
    if query_vec is None:
        return {}
    out: Dict[str, float] = {}
    for text in unique:
        vec = embeddings.get(text)
        if vec is None:
            continue
        dot = sum(a * b for a, b in zip(query_vec, vec))
        norm_a = sum(a * a for a in query_vec) ** 0.5
        norm_b = sum(b * b for b in vec) ** 0.5
        if norm_a and norm_b:
            out[text] = dot / (norm_a * norm_b)
    return out


def retrieve_best_rag_hit(sentence: str, catalog: Dict[str, Any]) -> Optional[RagHit]:
    """Pick the single best composition from interaction log + learned examples."""
    candidates: List[RagHit] = []

    blocks = get_top_k_blocks(sentence, k=15, ignore_enabled_flag=True)
    for block in blocks:
        sequence = _ratio_string_to_sequence(block.get("best_ratio", ""), catalog)
        if not sequence:
            continue
        embed_sim = float(block.get("similarity_to_current_request") or 0.0)
        candidates.append(
            RagHit(
                source="interaction_log",
                matched_text=block.get("target_smell", ""),
                embedding_similarity=embed_sim,
                rank_score=embed_sim,
                scent_sequence=sequence,
                best_similarity=block.get("best_similarity"),
            )
        )

    if settings.learned_examples_enabled:
        examples = load_examples()
        sentences = [ex.get("sentence", "") for ex in examples if ex.get("sentence")]
        sim_map = _embedding_similarity_map(sentence, sentences)
        for ex in examples:
            text = ex.get("sentence", "")
            embed_sim = sim_map.get(text, 0.0)
            if embed_sim <= 0:
                continue
            sequence = _learned_example_to_sequence(ex, catalog)
            if not sequence:
                continue
            rating = ex.get("rating") if isinstance(ex.get("rating"), int) else None
            candidates.append(
                RagHit(
                    source="learned_example",
                    matched_text=text,
                    embedding_similarity=embed_sim,
                    rank_score=embed_sim,
                    scent_sequence=sequence,
                    accept_rating=rating,
                    example_id=ex.get("id"),
                )
            )

    eligible = [
        hit for hit in candidates
        if hit.embedding_similarity >= settings.rag_compose_min_similarity
    ]
    if not eligible:
        return None

    # Each interaction-log block already stores the mixture from that session's
    # highest similarity round (_group_into_blocks). Among semantically eligible
    # matches, prefer the highest logged quality, then embedding similarity.
    eligible.sort(
        key=lambda hit: (_quality_score(hit), hit.embedding_similarity),
        reverse=True,
    )
    best = eligible[0]
    best.rank_score = round(_quality_score(best), 4)
    return best


def _rag_metadata(hit: RagHit) -> Dict[str, Any]:
    return {
        "used_rag": True,
        "source": hit.source,
        "matched_text": hit.matched_text,
        "embedding_similarity": round(hit.embedding_similarity, 4),
        "rank_score": hit.rank_score,
        "best_similarity": hit.best_similarity,
        "accept_rating": hit.accept_rating,
        "example_id": hit.example_id,
    }


def compose_with_rag_or_llm(
    sentence: str,
    catalog: Dict[str, Any],
    narrowed_catalog: Dict[str, Any],
    cartridge_status: Dict[str, Any],
) -> Tuple[ComposeResponse, Dict[str, Any]]:
    """Try RAG retrieval first; otherwise delegate to ensemble / single-shot LLM."""
    if settings.rag_compose_enabled:
        hit = retrieve_best_rag_hit(sentence, catalog)
        if hit:
            quality_note = ""
            if hit.best_similarity is not None:
                quality_note = f" Highest logged similarity for that target was {hit.best_similarity}/7."
            justification = (
                f"Retrieved from {hit.source.replace('_', ' ')}: closest match "
                f"\"{hit.matched_text}\" (embedding similarity {hit.embedding_similarity:.2f})."
                f"{quality_note} Using that session's best-rated mixture."
            )
            log.info(
                "RAG compose hit source=%s match=%r sim=%.3f",
                hit.source,
                hit.matched_text,
                hit.embedding_similarity,
            )
            return (
                ComposeResponse(scent_sequence=hit.scent_sequence, justification=justification),
                _rag_metadata(hit),
            )

    from .openai_client import classify_request_with_openai, compose_with_ensemble, compose_with_openai

    category = "abstract"
    if settings.ensemble_enabled:
        try:
            category = classify_request_with_openai(sentence).category
        except Exception as e:
            log.warning("Request classification failed (%s); defaulting to single-shot compose", e)

    if category == "concrete" and settings.ensemble_enabled:
        result = compose_with_ensemble(sentence, narrowed_catalog, cartridge_status)
    else:
        result = compose_with_openai(sentence, narrowed_catalog, cartridge_status)
    result = result.model_copy(update={"request_category": category})
    return result, {"used_rag": False}
