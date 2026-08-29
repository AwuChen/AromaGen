from __future__ import annotations

import base64
import io
import json
import logging
import statistics
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any, Dict, List, Optional, Type, TypeVar

from jinja2 import Environment, FileSystemLoader, select_autoescape
from openai import OpenAI
from pydantic import BaseModel

from .schemas import (
    ClassificationResponse,
    ComposeResponse,
    EnsembleValidationResponse,
    FeedbackRequest,
    FeedbackResponse,
    ScentItem,
    ValidationResponse,
)
from .settings import settings
from .example_bank import find_similar
from .interaction_retrieval import get_top_k_blocks

log = logging.getLogger(__name__)

T = TypeVar("T", bound=BaseModel)


def _apportion_counts(order: List[str], ratio_by_name: Dict[str, float], total_slots: int) -> Dict[str, int]:
    """Split total_slots among `order` proportional to ratio_by_name, guaranteeing
    every name gets at least 1 slot and the counts sum to exactly total_slots
    (largest-remainder / Hamilton apportionment)."""
    n = len(order)
    total_slots = max(total_slots, n)  # never fully silence an odorant
    total_ratio = sum(ratio_by_name.values()) or float(n)
    shares = {name: (ratio_by_name.get(name, 1.0) / total_ratio) * total_slots for name in order}
    counts = {name: max(1, int(shares[name])) for name in order}
    remainder = total_slots - sum(counts.values())
    if remainder > 0:
        by_fraction = sorted(order, key=lambda name: shares[name] - int(shares[name]), reverse=True)
        for i in range(remainder):
            counts[by_fraction[i % n]] += 1
    return counts


def _nearest_free_slot(slots: List[Optional[str]], pos: int) -> int:
    """Find the closest free slot to `pos`, searching both directions without
    wrapping around the ends. Wrapping would place a collision on the
    opposite side of the timeline from where it was supposed to land,
    undermining the even spacing this resolves collisions for."""
    if slots[pos] is None:
        return pos
    total = len(slots)
    for offset in range(1, total):
        later = pos + offset
        if later < total and slots[later] is None:
            return later
        earlier = pos - offset
        if earlier >= 0 and slots[earlier] is None:
            return earlier
    raise RuntimeError("No free slot available -- more occurrences than total slots")


def _interleave_by_count(order: List[str], counts: Dict[str, int]) -> List[str]:
    """Arrange each name's occurrences evenly across a single timeline of
    len == sum(counts) -- every odorant spread at its own uniform pace,
    with no strength-based bias toward earlier or later placement. Highest-
    count names are placed first so they claim their ideal even spacing;
    collisions resolve to the nearest free slot (not wrapped)."""
    total = sum(counts.values())
    slots: List[Optional[str]] = [None] * total
    placement_order = sorted(order, key=lambda n: counts[n], reverse=True)
    for name in placement_order:
        count = counts[name]
        for i in range(count):
            frac = (i + 0.5) / count
            pos = min(int(frac * total), total - 1)
            pos = _nearest_free_slot(slots, pos)
            slots[pos] = name
    return [name for name in slots if name]


def expand_to_pulse_sequence(
    scent_sequence: List[ScentItem],
    pulse_seconds: float,
    rounds: int,
) -> List[ScentItem]:
    """Deterministically turn the model's conceptual scent pick into an
    interleaved, ratio-weighted pulse train.

    Every distinct odorant in scent_sequence (in first-appearance order,
    ratios summed if it appears more than once) gets a share of a
    `rounds * distinct_odorant_count` pulse budget proportional to its
    ratio -- e.g. two odorants at 60/40 with rounds=8 get a 16-pulse budget
    split ~10/6 instead of 8/8. This keeps total playback duration for a
    given odorant count consistent with the old uniform scheme (so raising
    `rounds` still means more perceptible exposure time), while now also
    reflecting how central vs. supporting each odorant is to the blend.

    Occurrences are spread evenly across the timeline for every odorant
    regardless of `strength` -- no odorant is pushed earlier or later than
    its ratio-weighted share would naturally place it. (Earlier versions of
    this system skewed strong-smelling odorants later and weak ones earlier;
    that bias was removed in favor of even mixing.)

    The model's own per-scent durations (opening/heart/closing timing) are
    intentionally not used here; this is a hardware-delivery experiment
    (rapid, ratio-weighted alternation to encourage perceptual blending)
    separate from the model's compositional reasoning, so it's implemented
    as a deterministic post-processing step rather than asked of the model.
    """
    order: List[str] = []
    ratio_by_name: Dict[str, float] = {}
    for item in scent_sequence:
        if item.scent_name not in ratio_by_name:
            order.append(item.scent_name)
            ratio_by_name[item.scent_name] = 0.0
        ratio_by_name[item.scent_name] += max(item.ratio, 0.0)

    if not order:
        return []

    total_slots = rounds * len(order)
    counts = _apportion_counts(order, ratio_by_name, total_slots)
    names = _interleave_by_count(order, counts)
    return [ScentItem(scent_name=name, scent_duration=pulse_seconds) for name in names]


def transcribe_audio(audio_bytes: bytes, filename: str = "audio.webm") -> str:
    """Transcribe audio using OpenAI Whisper API."""
    client = OpenAI(api_key=settings.openai_api_key)
    file_like = io.BytesIO(audio_bytes)
    file_like.name = filename
    response = client.audio.transcriptions.create(model="whisper-1", file=file_like)
    return response.text


IMAGE_DESCRIPTION_PROMPT = (
    "Describe this image as sensory prose suitable for composing a scent experience. "
    "Focus on smells, atmosphere, mood, textures, food, nature, and emotional tone. "
    "Write 1-3 short sentences in evocative descriptive language. "
    "Do not mention that this is an image."
)


def describe_image(image_bytes: bytes, content_type: str) -> str:
    """Describe an uploaded image using OpenAI vision."""
    client = OpenAI(api_key=settings.openai_api_key)
    mime = content_type or "image/jpeg"
    data_url = f"data:{mime};base64,{base64.standard_b64encode(image_bytes).decode('ascii')}"
    response = client.chat.completions.create(
        model=settings.openai_vision_model,
        messages=[
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": IMAGE_DESCRIPTION_PROMPT},
                    {"type": "image_url", "image_url": {"url": data_url}},
                ],
            }
        ],
        max_completion_tokens=300,
    )
    text = response.choices[0].message.content
    if not text:
        raise ValueError("No description returned for image")
    return text.strip()


def _render_prompt(
    template_name: str,
    scents: Dict[str, Any],
    cartridge_status: Optional[Dict[str, Any]] = None,
    learned_examples: Optional[List[Dict[str, Any]]] = None,
    interaction_precedent: Optional[List[Dict[str, Any]]] = None,
) -> str:
    env = Environment(
        loader=FileSystemLoader(settings.prompts_dir),
        autoescape=select_autoescape(enabled_extensions=("j2",)),
        trim_blocks=True,
        lstrip_blocks=True,
    )
    template = env.get_template(template_name)
    scents_json = json.dumps(scents, ensure_ascii=False, indent=4)
    cartridge_status_json = json.dumps(cartridge_status or {}, ensure_ascii=False, indent=4)
    learned_examples_json = json.dumps(learned_examples or [], ensure_ascii=False, indent=4)
    interaction_precedent_json = json.dumps(interaction_precedent or [], ensure_ascii=False, indent=4)
    return template.render(
        scents_json=scents_json,
        cartridge_status_json=cartridge_status_json,
        learned_examples=learned_examples or [],
        learned_examples_json=learned_examples_json,
        interaction_precedent=interaction_precedent or [],
        interaction_precedent_json=interaction_precedent_json,
        sequence_total_seconds=settings.sequence_total_seconds,
        scent_duration_max=settings.scent_duration_max,
    )


def _build_schema(scents: Dict[str, Any], *, include_changes_made: bool = False) -> Dict[str, Any]:
    scent_names = list(scents.keys())
    properties: Dict[str, Any] = {
        "scent_sequence": {
            "type": "array",
            "minItems": 1,
            "items": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "scent_name": {"type": "string", "enum": scent_names},
                    "scent_duration": {
                        "type": "integer",
                        "minimum": 1,
                        "maximum": settings.scent_duration_max,
                    },
                    "ratio": {
                        "type": "number",
                        "exclusiveMinimum": 0,
                        "maximum": 1,
                    },
                },
                "required": ["scent_name", "scent_duration", "ratio"],
            },
        },
        "justification": {"type": "string"},
    }
    required = ["scent_sequence", "justification"]
    if include_changes_made:
        properties["changes_made"] = {"type": "string"}
        required.append("changes_made")

    return {
        "type": "object",
        "additionalProperties": False,
        "properties": properties,
        "required": required,
    }


def _build_validation_schema(candidate_names: List[str]) -> Dict[str, Any]:
    return {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "kept_scent_names": {
                "type": "array",
                "minItems": 1,
                "items": {"type": "string", "enum": candidate_names},
            },
            "reasoning": {"type": "string"},
        },
        "required": ["kept_scent_names", "reasoning"],
    }


def _extract_message_text(response: Any) -> str:
    choice = response.choices[0]
    message = choice.message
    if getattr(message, "content", None):
        return message.content
    if getattr(message, "parsed", None) is not None:
        parsed = message.parsed
        if isinstance(parsed, BaseModel):
            return parsed.model_dump_json()
        return json.dumps(parsed)
    raise ValueError("No text content in chat completion response")


def _chat_parse(
    client: OpenAI,
    *,
    system_prompt: str,
    user_message: str,
    response_model: Type[T],
    max_completion_tokens: Optional[int] = None,
    temperature: Optional[float] = None,
) -> T:
    """Structured output via Chat Completions (works with gpt-4o-mini and gpt-5)."""
    kwargs: Dict[str, Any] = {
        "model": settings.openai_model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message},
        ],
        "response_format": response_model,
    }
    if max_completion_tokens is not None:
        kwargs["max_completion_tokens"] = max_completion_tokens
    if temperature is not None:
        kwargs["temperature"] = temperature

    response = client.chat.completions.parse(**kwargs)
    parsed = response.choices[0].message.parsed
    if parsed is None:
        raise ValueError("Model returned no parsed structured output")
    if isinstance(parsed, response_model):
        return parsed
    return response_model.model_validate(parsed)


def _chat_json_schema_fallback(
    client: OpenAI,
    *,
    system_prompt: str,
    user_message: str,
    response_model: Type[T],
    schema: Dict[str, Any],
    schema_name: str,
    max_completion_tokens: Optional[int] = None,
    temperature: Optional[float] = None,
) -> T:
    kwargs: Dict[str, Any] = {
        "model": settings.openai_model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message},
        ],
        "response_format": {
            "type": "json_schema",
            "json_schema": {
                "name": schema_name,
                "schema": schema,
                "strict": True,
            },
        },
    }
    if max_completion_tokens is not None:
        kwargs["max_completion_tokens"] = max_completion_tokens
    if temperature is not None:
        kwargs["temperature"] = temperature

    response = client.chat.completions.create(**kwargs)
    raw_text = _extract_message_text(response)
    return response_model.model_validate_json(raw_text)


def _complete_structured(
    client: OpenAI,
    *,
    system_prompt: str,
    user_message: str,
    response_model: Type[T],
    schema: Dict[str, Any],
    schema_name: str,
    max_completion_tokens: Optional[int] = None,
    temperature: Optional[float] = None,
) -> T:
    # json_schema (with an explicit "enum" on scent_name) is tried first --
    # it's the only path that actually restricts scent_name to the current
    # catalog. chat.completions.parse(response_format=response_model) derives
    # its schema straight from ScentItem's field types, and scent_name is a
    # plain `str` there (no Literal), so that path lets the model return any
    # string at all; using it as primary meant validate_composition() was
    # routinely catching hallucinated-but-plausible names instead of that
    # being a rare defense-in-depth backstop.
    try:
        return _chat_json_schema_fallback(
            client,
            system_prompt=system_prompt,
            user_message=user_message,
            response_model=response_model,
            schema=schema,
            schema_name=schema_name,
            max_completion_tokens=max_completion_tokens,
            temperature=temperature,
        )
    except Exception as primary_err:
        log.warning(
            "json_schema completion failed (%s), trying chat.completions.parse fallback",
            primary_err,
        )
        try:
            return _chat_parse(
                client,
                system_prompt=system_prompt,
                user_message=user_message,
                response_model=response_model,
                max_completion_tokens=max_completion_tokens,
                temperature=temperature,
            )
        except Exception as fallback_err:
            raise RuntimeError(
                f"Structured completion failed: {primary_err}; fallback: {fallback_err}"
            ) from fallback_err


def validate_relevance_with_openai(
    sentence: str,
    scent_sequence: List[ScentItem],
    scents_catalog: Dict[str, Any],
) -> ValidationResponse:
    """Second-layer AI pass: given the first AI's chosen odorants, remove any
    that don't actually belong in the target smell (e.g. Peppermint proposed
    for a "sweaty" request). Runs as an independent model call with its own
    prompt so it isn't anchored to the first AI's own reasoning."""
    candidates = [
        {
            "scent_name": item.scent_name,
            "category": scents_catalog.get(item.scent_name, {}).get("category", ""),
            "note": scents_catalog.get(item.scent_name, {}).get("note", ""),
            "ratio": item.ratio,
        }
        for item in scent_sequence
    ]
    candidate_names = [c["scent_name"] for c in candidates]

    env = Environment(
        loader=FileSystemLoader(settings.prompts_dir),
        autoescape=select_autoescape(enabled_extensions=("j2",)),
        trim_blocks=True,
        lstrip_blocks=True,
    )
    template = env.get_template("validation_prompt.j2")
    prompt = template.render(
        sentence=sentence,
        candidates_json=json.dumps(candidates, ensure_ascii=False, indent=2),
    )

    client = OpenAI(api_key=settings.openai_api_key)
    schema = _build_validation_schema(candidate_names)
    return _complete_structured(
        client,
        system_prompt=prompt,
        user_message=sentence,
        response_model=ValidationResponse,
        schema=schema,
        schema_name="OdorantRelevanceCheck",
        max_completion_tokens=1024,
    )


def compose_with_openai(
    sentence: str,
    scents: Dict[str, Any],
    cartridge_status: Optional[Dict[str, Any]] = None,
) -> ComposeResponse:
    learned_examples = find_similar(sentence)
    interaction_precedent = (
        get_top_k_blocks(sentence) if settings.interaction_retrieval_enabled else []
    )
    system_prompt = _render_prompt(
        "system_prompt.j2",
        scents,
        cartridge_status,
        learned_examples=learned_examples,
        interaction_precedent=interaction_precedent,
    )
    client = OpenAI(api_key=settings.openai_api_key)
    schema = _build_schema(scents)
    return _complete_structured(
        client,
        system_prompt=system_prompt,
        user_message=sentence,
        response_model=ComposeResponse,
        schema=schema,
        schema_name="ScentSequence",
        max_completion_tokens=2048,
    )


# ---------------------------------------------------------------------------
# Self-consistency ensemble for concrete-smell requests
#
# Rationale: a single zero-shot call is stochastic, so the same concrete
# request ("strawberry") can yield noticeably different odorant picks across
# runs -- undesirable for something that should smell consistent. For
# requests classified as concrete (not abstract, where variability is
# actually desirable), we instead run N independent predictor calls at a
# controlled nonzero temperature, tally votes per odorant, auto-accept
# strong-consensus picks, send moderate/weak picks to a separate validator
# call, aggregate ratios by median (not mean, so one outlier prediction
# doesn't skew the result), and record a stability/confidence summary.
# ---------------------------------------------------------------------------


def classify_request_with_openai(sentence: str) -> ClassificationResponse:
    """Cheap upfront call: is this request a concrete, tangible real-world
    smell (ensemble path) or an abstract mood/memory/brand/scene (existing
    single-shot path, where run-to-run variability is fine)?"""
    env = Environment(
        loader=FileSystemLoader(settings.prompts_dir),
        autoescape=select_autoescape(enabled_extensions=("j2",)),
        trim_blocks=True,
        lstrip_blocks=True,
    )
    template = env.get_template("classify_request_prompt.j2")
    prompt = template.render(sentence=sentence)
    client = OpenAI(api_key=settings.openai_api_key)
    schema = {
        "type": "object",
        "additionalProperties": False,
        "properties": {"category": {"type": "string", "enum": ["concrete", "abstract"]}},
        "required": ["category"],
    }
    return _complete_structured(
        client,
        system_prompt=prompt,
        user_message=sentence,
        response_model=ClassificationResponse,
        schema=schema,
        schema_name="RequestClassification",
        max_completion_tokens=50,
    )


def _compose_predictor_call(
    sentence: str,
    scents: Dict[str, Any],
    cartridge_status: Optional[Dict[str, Any]],
    temperature: float,
) -> ComposeResponse:
    """One independent ensemble predictor run -- same idea as compose_with_openai
    but using the concrete-only predictor prompt (no abstract/beats branch,
    since classification already determined this request is concrete) and an
    explicit nonzero temperature for diversity across the ensemble."""
    system_prompt = _render_prompt("predictor_prompt.j2", scents, cartridge_status)
    client = OpenAI(api_key=settings.openai_api_key)
    schema = _build_schema(scents)
    return _complete_structured(
        client,
        system_prompt=system_prompt,
        user_message=sentence,
        response_model=ComposeResponse,
        schema=schema,
        schema_name="EnsemblePredictorScentSequence",
        max_completion_tokens=1024,
        temperature=temperature,
    )


def _run_predictors(
    sentence: str,
    scents: Dict[str, Any],
    cartridge_status: Optional[Dict[str, Any]],
    count: int,
    temperature: float,
) -> List[ComposeResponse]:
    """Run `count` predictor calls in parallel (they're independent, blocking
    HTTP calls, so latency is ~one call's worth, not count calls' worth).
    A predictor that errors is dropped, not fatal -- the ensemble degrades
    gracefully to fewer votes rather than failing the whole request."""
    results: List[ComposeResponse] = []
    with ThreadPoolExecutor(max_workers=count) as executor:
        futures = [
            executor.submit(_compose_predictor_call, sentence, scents, cartridge_status, temperature)
            for _ in range(count)
        ]
        for future in as_completed(futures):
            try:
                results.append(future.result())
            except Exception as e:
                log.warning("Ensemble predictor call failed (%s); continuing with fewer votes", e)
    return results


def _tally_votes(
    predictor_results: List[ComposeResponse],
) -> tuple[Dict[str, int], Dict[str, List[float]], Dict[str, List[float]]]:
    votes: Dict[str, int] = defaultdict(int)
    ratios_by_name: Dict[str, List[float]] = defaultdict(list)
    durations_by_name: Dict[str, List[float]] = defaultdict(list)
    for result in predictor_results:
        seen: set = set()
        for item in result.scent_sequence:
            if item.scent_name in seen:
                continue  # one vote per odorant per predictor, even if it somehow repeats
            seen.add(item.scent_name)
            votes[item.scent_name] += 1
            ratios_by_name[item.scent_name].append(item.ratio)
            durations_by_name[item.scent_name].append(item.scent_duration)
    return dict(votes), dict(ratios_by_name), dict(durations_by_name)


def validate_ensemble_candidates_with_openai(
    sentence: str,
    candidate_names: List[str],
    votes: Dict[str, int],
    strong_names: List[str],
    scents_catalog: Dict[str, Any],
    n_predictors: int,
    strong_threshold: int,
) -> EnsembleValidationResponse:
    """Stage 4: a separate model call judges which moderate/weak-consensus
    odorants are essential enough to keep, guided by "would removing this
    make an essential perceptual quality impossible to express?" -- not a
    fresh recipe, just a keep/discard call on the candidates it's given."""
    candidates = [
        {
            "scent_name": name,
            "category": scents_catalog.get(name, {}).get("category", ""),
            "note": scents_catalog.get(name, {}).get("note", ""),
            "votes": f"{votes.get(name, 0)}/{n_predictors}",
        }
        for name in candidate_names
    ]
    env = Environment(
        loader=FileSystemLoader(settings.prompts_dir),
        autoescape=select_autoescape(enabled_extensions=("j2",)),
        trim_blocks=True,
        lstrip_blocks=True,
    )
    template = env.get_template("ensemble_validator_prompt.j2")
    prompt = template.render(
        sentence=sentence,
        n_predictors=n_predictors,
        strong_threshold=strong_threshold,
        strong_names_json=json.dumps(strong_names, ensure_ascii=False),
        candidates_json=json.dumps(candidates, ensure_ascii=False, indent=2),
    )
    client = OpenAI(api_key=settings.openai_api_key)
    schema = {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "kept_scent_names": {
                "type": "array",
                "items": {"type": "string", "enum": candidate_names},
            },
            "reasoning": {"type": "string"},
        },
        "required": ["kept_scent_names", "reasoning"],
    }
    return _complete_structured(
        client,
        system_prompt=prompt,
        user_message=sentence,
        response_model=EnsembleValidationResponse,
        schema=schema,
        schema_name="EnsembleConsensusValidation",
        max_completion_tokens=512,
    )


def _classify_confidence(
    final_names: List[str],
    votes: Dict[str, int],
    ratios_by_name: Dict[str, List[float]],
    n_predictors: int,
    strong_threshold: int,
    weak_threshold: int,
) -> str:
    """High: every retained odorant has strong-ish support and tightly grouped
    ratios. Medium: support/spread is looser but nothing was a weak-tier
    rescue. Low: a weak-tier (validator-rescued) odorant survived, no odorant
    reached strong consensus at all, or ratio predictions disagree sharply --
    any of these mean the result is one specific ensemble run away from
    looking different, which is exactly what should trigger the retry round."""
    if not final_names:
        return "low"
    has_weak_rescue = any(votes.get(n, 0) < weak_threshold for n in final_names)
    has_strong_anchor = any(votes.get(n, 0) >= strong_threshold for n in final_names)
    max_spread = 0.0
    min_vote_frac = 1.0
    for n in final_names:
        ratios = ratios_by_name.get(n, [])
        if len(ratios) > 1:
            max_spread = max(max_spread, max(ratios) - min(ratios))
        min_vote_frac = min(min_vote_frac, votes.get(n, 0) / n_predictors)
    if has_weak_rescue or not has_strong_anchor or max_spread > 0.4:
        return "low"
    if min_vote_frac >= 0.7 and max_spread <= 0.2:
        return "high"
    return "medium"


def _build_ensemble_justification(
    final_names: List[str],
    votes: Dict[str, int],
    ratios: Dict[str, float],
    n_predictors: int,
    strong_threshold: int,
    strong_names: List[str],
    validator_reasoning: str,
    confidence: str,
    retried: bool,
) -> str:
    parts = []
    for name in final_names:
        v = votes.get(name, 0)
        tier = "strong consensus" if name in strong_names else "kept by validator"
        parts.append(f"{name} ({v}/{n_predictors} votes, {tier}, {ratios[name]*100:.0f}% of blend)")
    retry_note = " (a second predictor round ran after the first came back low-confidence)" if retried else ""
    return (
        f"Ensemble consensus across {n_predictors} independent runs{retry_note}: "
        + "; ".join(parts)
        + f". Validator on moderate/weak candidates: {validator_reasoning} "
        + f"Confidence: {confidence}."
    )


def compose_with_ensemble(
    sentence: str,
    scents: Dict[str, Any],
    cartridge_status: Optional[Dict[str, Any]] = None,
) -> ComposeResponse:
    """Stages 1, 3-6 of the self-consistency ensemble pipeline for concrete
    requests. Downstream steps (catalog validation, the existing relevance
    validator, compatibility warnings, pulse expansion) are unchanged and
    run on this function's output exactly as they do for compose_with_openai."""
    n = settings.ensemble_predictor_count
    strong_threshold = settings.ensemble_strong_threshold
    weak_threshold = settings.ensemble_weak_threshold

    predictor_results = _run_predictors(sentence, scents, cartridge_status, n, settings.ensemble_temperature)
    if not predictor_results:
        raise RuntimeError("All ensemble predictor calls failed")

    def _resolve(predictor_results: List[ComposeResponse]) -> Dict[str, Any]:
        n_eff = len(predictor_results)
        votes, ratios_by_name, durations_by_name = _tally_votes(predictor_results)
        strong_names = [name for name, v in votes.items() if v >= strong_threshold]
        candidate_names = [name for name, v in votes.items() if v < strong_threshold]

        if candidate_names:
            validation = validate_ensemble_candidates_with_openai(
                sentence, candidate_names, votes, strong_names, scents, n_eff, strong_threshold
            )
            validator_kept = validation.kept_scent_names
            validator_reasoning = validation.reasoning
        else:
            validator_kept = []
            validator_reasoning = "No moderate/weak-consensus candidates; strong-consensus set alone was used."

        final_names = strong_names + [name for name in validator_kept if name not in strong_names]
        if not final_names and votes:
            # Degenerate case (e.g. every candidate rejected and nothing reached
            # strong consensus): fall back to the single most-voted odorant
            # rather than returning an empty composition.
            final_names = [max(votes, key=votes.get)]

        confidence = _classify_confidence(
            final_names, votes, ratios_by_name, n_eff, strong_threshold, weak_threshold
        )
        return {
            "n_eff": n_eff,
            "votes": votes,
            "ratios_by_name": ratios_by_name,
            "durations_by_name": durations_by_name,
            "strong_names": strong_names,
            "candidate_names": candidate_names,
            "validator_kept": validator_kept,
            "validator_reasoning": validator_reasoning,
            "final_names": final_names,
            "confidence": confidence,
        }

    resolved = _resolve(predictor_results)
    retried = False
    if resolved["confidence"] == "low" and settings.ensemble_retry_predictor_count > 0:
        retried = True
        extra_results = _run_predictors(
            sentence, scents, cartridge_status, settings.ensemble_retry_predictor_count, settings.ensemble_temperature
        )
        predictor_results = predictor_results + extra_results
        resolved = _resolve(predictor_results)

    final_names = resolved["final_names"]
    votes = resolved["votes"]
    ratios_by_name = resolved["ratios_by_name"]
    durations_by_name = resolved["durations_by_name"]
    n_eff = resolved["n_eff"]

    # Stage 5: median ratio per retained odorant (robust to one outlier
    # prediction), renormalized so the final set sums to 1.
    median_ratios = {
        name: statistics.median(ratios_by_name[name]) if ratios_by_name.get(name) else (1.0 / len(final_names))
        for name in final_names
    }
    ratio_total = sum(median_ratios.values()) or 1.0
    final_ratios = {name: median_ratios[name] / ratio_total for name in final_names}
    final_durations = {
        name: statistics.median(durations_by_name[name]) if durations_by_name.get(name) else 10.0
        for name in final_names
    }

    # Most-dominant-first ordering for a sensible read of the final recipe.
    final_names_sorted = sorted(final_names, key=lambda n: -final_ratios[n])

    scent_sequence = [
        ScentItem(scent_name=name, scent_duration=final_durations[name], ratio=final_ratios[name])
        for name in final_names_sorted
    ]

    justification = _build_ensemble_justification(
        final_names_sorted,
        votes,
        final_ratios,
        n_eff,
        strong_threshold,
        resolved["strong_names"],
        resolved["validator_reasoning"],
        resolved["confidence"],
        retried,
    )

    stability = {
        "n_predictors": n_eff,
        "retried": retried,
        "votes": votes,
        "vote_fraction": {name: round(v / n_eff, 3) for name, v in votes.items()},
        "strong_consensus": resolved["strong_names"],
        "moderate_or_weak_candidates": resolved["candidate_names"],
        "validator_kept": resolved["validator_kept"],
        "validator_reasoning": resolved["validator_reasoning"],
        "final_ingredients": final_names_sorted,
        "ratio_spread": {
            name: round(max(ratios_by_name[name]) - min(ratios_by_name[name]), 3)
            if len(ratios_by_name.get(name, [])) > 1 else 0.0
            for name in final_names
        },
        "confidence": resolved["confidence"],
    }

    return ComposeResponse(
        scent_sequence=scent_sequence,
        justification=justification,
        request_category="concrete",
        ensemble_stability=stability,
    )


def _build_feedback_user_message(request: FeedbackRequest) -> str:
    """Format a structured user message for the feedback/revision flow."""
    current_seq = [
        {"scent_name": s.scent_name, "scent_duration": s.scent_duration}
        for s in request.original_sequence
    ]
    if request.prior_rounds:
        last = request.prior_rounds[-1]
        current_seq = [
            {"scent_name": s.scent_name, "scent_duration": s.scent_duration}
            for s in last.resulting_sequence
        ]

    seq_json = json.dumps(current_seq, indent=2)

    history_lines: List[str] = []
    for i, r in enumerate(request.prior_rounds, 1):
        history_lines.append(f"  Round {i}: \"{r.feedback_text}\" → {r.changes_made}")
    history_section = "\n".join(history_lines) if history_lines else "(none)"

    return (
        f"ORIGINAL REQUEST:\n{request.original_sentence}\n\n"
        f"CURRENT SEQUENCE:\n```json\n{seq_json}\n```\n\n"
        f"PRIOR FEEDBACK HISTORY:\n{history_section}\n\n"
        f">>> LATEST FEEDBACK <<<\n{request.latest_feedback}"
    )


def refine_with_openai(
    request: FeedbackRequest,
    scents: Dict[str, Any],
    cartridge_status: Optional[Dict[str, Any]] = None,
) -> FeedbackResponse:
    """Refine an existing scent composition based on user feedback."""
    system_prompt = _render_prompt("feedback_prompt.j2", scents, cartridge_status)
    user_message = _build_feedback_user_message(request)
    client = OpenAI(api_key=settings.openai_api_key)
    schema = _build_schema(scents, include_changes_made=True)
    return _complete_structured(
        client,
        system_prompt=system_prompt,
        user_message=user_message,
        response_model=FeedbackResponse,
        schema=schema,
        schema_name="ScentRevision",
        max_completion_tokens=4096,
    )
