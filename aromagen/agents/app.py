from __future__ import annotations

import logging
import math
from typing import Any, Dict, List, Optional, Tuple

import httpx
from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware

from .schemas import (
    AcceptRequest,
    AcceptResponse,
    ComposeRequest,
    ComposeResponse,
    FeedbackRequest,
    FeedbackResponse,
    LogInteractionRequest,
    LogInteractionResponse,
    ScentItem,
    SimplexAnchor,
    SimplexBlendResponse,
    SimplexInterpolateRequest,
    SimplexPointRequest,
    SimplexPrepareAnchorsRequest,
    DevicePlaySequenceRequest,
)
from .simplex_triangle import prepare_triangle
from .simplex import (
    DEFAULT_ANCHOR_PRESETS,
    blend_vectors,
    barycentric_from_point,
    load_corpus_vectors,
    nearest_corpus_recipe,
    sequence_to_vector,
    vector_to_sequence,
)
from .settings import settings
from .openai_client import (
    classify_request_with_openai,
    compose_with_ensemble,
    compose_with_openai,
    describe_image,
    expand_to_pulse_sequence,
    refine_with_openai,
    transcribe_audio,
    validate_relevance_with_openai,
)
from .conversation_logger import append_event, new_session_id
from .example_bank import add_example
from .interaction_retrieval import append_local_log
from .cartridge import (
    build_catalog_scents,
    check_compatibility_warnings,
    get_cartridge_status,
    load_cartridge_config,
    validate_composition,
)
from .descriptor_filter import filter_relevant_scents

log = logging.getLogger(__name__)


def _format_pulse_summary(pulse_sequence: List[ScentItem]) -> str:
    """Run-length-encoded, human-readable description of the actual pulse
    train (e.g. "Vanilla x7, Peppermint x1, Vanilla x3, ...") -- the AI can't
    write this into its own justification since the pulse train is computed
    deterministically after the AI call, from `ratio` and `strength`."""
    if not pulse_sequence:
        return ""
    groups: List[str] = []
    current_name = pulse_sequence[0].scent_name
    current_count = 1
    for item in pulse_sequence[1:]:
        if item.scent_name == current_name:
            current_count += 1
        else:
            groups.append(f"{current_name} x{current_count}")
            current_name = item.scent_name
            current_count = 1
    groups.append(f"{current_name} x{current_count}")

    pulse_seconds = pulse_sequence[0].scent_duration
    total_seconds = sum(item.scent_duration for item in pulse_sequence)
    return (
        f"Device playback -- {len(pulse_sequence)} pulses, {pulse_seconds:g}s each, "
        f"{total_seconds:g}s total: " + ", ".join(groups)
    )


def _validate_and_expand(
    sentence: str,
    scent_sequence: List[ScentItem],
    catalog: Dict[str, Dict[str, Any]],
    justification: str,
) -> Dict[str, Any]:
    """Run the second-layer relevance validator, then expand the surviving
    (validated) odorants into the ratio-weighted pulse train. Falls back to
    the unfiltered sequence if the validator call itself fails, so a
    validator hiccup doesn't take down an otherwise-good composition."""
    candidate_names: List[str] = []
    for item in scent_sequence:
        if item.scent_name not in candidate_names:
            candidate_names.append(item.scent_name)

    if not settings.validation_layer_enabled:
        validated_sequence = scent_sequence
        removed_scents = []
        validation_reasoning = "Validation layer disabled (VALIDATION_LAYER_ENABLED=false)."
    else:
        try:
            validation = validate_relevance_with_openai(sentence, scent_sequence, catalog)
            kept = set(validation.kept_scent_names)
            validated_sequence = [item for item in scent_sequence if item.scent_name in kept] or scent_sequence
            # Derived from kept, not asked of the model separately -- guarantees
            # removed can never disagree with what was actually filtered.
            removed_scents = [name for name in candidate_names if name not in kept]
            validation_reasoning = validation.reasoning
        except Exception as e:
            log.warning("Relevance validation failed (%s); using unfiltered sequence", e)
            validated_sequence = scent_sequence
            removed_scents = []
            validation_reasoning = f"Validation skipped due to an error: {e}"

    compatibility_warnings = check_compatibility_warnings(validated_sequence, catalog)
    pulse_sequence = expand_to_pulse_sequence(
        validated_sequence, settings.pulse_seconds, settings.pulse_rounds
    )
    pulse_summary = _format_pulse_summary(pulse_sequence)
    combined_justification = f"{justification}\n\n{pulse_summary}" if pulse_summary else justification
    return {
        "validated_sequence": validated_sequence,
        "removed_scents": removed_scents,
        "validation_reasoning": validation_reasoning,
        "compatibility_warnings": compatibility_warnings,
        "pulse_sequence": pulse_sequence,
        "justification": combined_justification,
    }


def _cartridge_context() -> Tuple[Dict[str, Any], Dict[str, Dict[str, Any]]]:
    config = load_cartridge_config(settings.cartridge_sets_path)
    catalog = build_catalog_scents(config)
    return config, catalog


def _simplex_blend_from_weights(
    anchors: List[SimplexAnchor],
    weights: List[float],
    *,
    use_corpus_nearest: bool,
) -> SimplexBlendResponse:
    try:
        _, catalog = _cartridge_context()
    except FileNotFoundError as e:
        raise HTTPException(status_code=500, detail=str(e))

    odorant_names = list(catalog.keys())
    sequences = [anchor.scent_sequence for anchor in anchors]
    for seq in sequences:
        validate_composition(seq, catalog)

    vectors = [sequence_to_vector(seq, odorant_names) for seq in sequences]
    blended = blend_vectors(vectors[0], vectors[1], vectors[2], (weights[0], weights[1], weights[2]))
    corpus = load_corpus_vectors(settings.learned_examples_path, odorant_names)
    corpus_match = nearest_corpus_recipe(blended, corpus) if use_corpus_nearest else None
    corpus_max_distance = 0.35

    if (
        use_corpus_nearest
        and corpus_match
        and corpus_match.get("scent_sequence")
        and float(corpus_match.get("distance", 1.0)) <= corpus_max_distance
    ):
        sequence = corpus_match["scent_sequence"]
        source = "corpus"
    else:
        sequence = vector_to_sequence(blended, pulse_seconds=settings.pulse_seconds)
        source = "blend"

    validate_composition(sequence, catalog)
    compatibility_warnings = check_compatibility_warnings(sequence, catalog)
    pulse_sequence = expand_to_pulse_sequence(sequence, settings.pulse_seconds, settings.pulse_rounds)
    w_sum = sum(weights)
    norm_weights = [w / w_sum for w in weights] if w_sum > 0 else [1 / 3, 1 / 3, 1 / 3]

    return SimplexBlendResponse(
        weights=norm_weights,
        scent_sequence=sequence,
        validated_sequence=sequence,
        pulse_sequence=pulse_sequence,
        vector=blended,
        compatibility_warnings=compatibility_warnings,
        corpus_match=corpus_match,
        source=source,
    )


def load_scents() -> Dict[str, Any]:
    """Return the full (fixed, 12-odorant) scent catalog for AI composition."""
    _, catalog = _cartridge_context()
    return catalog


app = FastAPI(title="AromaGen Scent Composer")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"]
)


@app.get("/health")
def health() -> Dict[str, Any]:
    ble_ok = False
    try:
        with httpx.Client(timeout=2.0) as client:
            resp = client.get(f"{settings.ble_backend_url.rstrip('/')}/health")
            ble_ok = resp.status_code == 200
    except Exception:
        ble_ok = False
    return {
        "status": "ok",
        "ble_backend_url": settings.ble_backend_url,
        "ble_backend_reachable": ble_ok,
        "interaction_logging_configured": bool(
            settings.interaction_log_apps_script_url and settings.interaction_log_token
        ),
    }


@app.post("/device/play_sequence")
async def device_play_sequence(request: DevicePlaySequenceRequest) -> Dict[str, Any]:
    """Forward pulse train to the Flask BLE backend (browser only talks to :8000)."""
    url = f"{settings.ble_backend_url.rstrip('/')}/play_sequence"
    payload = {"sequence": [item.model_dump() for item in request.sequence]}
    try:
        async with httpx.AsyncClient(timeout=120.0) as client:
            resp = await client.post(url, json=payload)
    except httpx.ConnectError:
        raise HTTPException(
            status_code=503,
            detail=(
                f"BLE backend not reachable at {settings.ble_backend_url}. "
                "Start it with ./start_ble_backend.sh or the BLE tab from ./start_all.sh."
            ),
        )
    except httpx.HTTPError as e:
        raise HTTPException(status_code=502, detail=f"BLE backend request failed: {e}")

    try:
        body = resp.json()
    except ValueError:
        raise HTTPException(
            status_code=502,
            detail=f"BLE backend returned non-JSON (HTTP {resp.status_code})",
        )
    if resp.status_code >= 400:
        raise HTTPException(status_code=resp.status_code, detail=body.get("message") or body)
    return body


@app.get("/cartridge/status")
def cartridge_status() -> Dict[str, Any]:
    try:
        config, catalog = _cartridge_context()
    except FileNotFoundError as e:
        raise HTTPException(status_code=500, detail=str(e))

    status = get_cartridge_status(config)
    return {
        **status,
        "active_scents": catalog,
    }


@app.get("/cartridge/active")
def cartridge_active() -> Dict[str, Any]:
    """The fixed 12-odorant catalog with slot locations (for playback)."""
    try:
        config, catalog = _cartridge_context()
    except FileNotFoundError as e:
        raise HTTPException(status_code=500, detail=str(e))

    return {
        "status": get_cartridge_status(config),
        "scents": catalog,
    }


@app.get("/simplex/presets")
def simplex_presets() -> Dict[str, Any]:
    """Fixed token-labeled anchor recipes for offline triangle navigation."""
    anchors: List[Dict[str, Any]] = []
    for preset in DEFAULT_ANCHOR_PRESETS:
        sequence = [ScentItem(**item) for item in preset["scent_sequence"]]
        pulse = expand_to_pulse_sequence(sequence, settings.pulse_seconds, settings.pulse_rounds)
        anchors.append(
            {
                **preset,
                "scent_sequence": [item.model_dump() for item in sequence],
                "pulse_sequence": [item.model_dump() for item in pulse],
            }
        )
    return {"anchors": anchors}


@app.post("/simplex/interpolate", response_model=SimplexBlendResponse)
def simplex_interpolate(request: SimplexInterpolateRequest) -> SimplexBlendResponse:
    try:
        return _simplex_blend_from_weights(
            request.anchors,
            request.weights,
            use_corpus_nearest=request.use_corpus_nearest,
        )
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))


@app.post("/simplex/from_point", response_model=SimplexBlendResponse)
def simplex_from_point(request: SimplexPointRequest) -> SimplexBlendResponse:
    """Map a click in normalized triangle space to barycentric weights, then blend."""
    # UI uses A top, B bottom-left, C bottom-right in unit coordinates.
    ax, ay = 0.5, math.sqrt(3) / 2
    bx, by = 0.0, 0.0
    cx, cy = 1.0, 0.0
    weights = barycentric_from_point(
        request.point_x,
        request.point_y,
        ax,
        ay,
        bx,
        by,
        cx,
        cy,
    )
    try:
        return _simplex_blend_from_weights(
            request.anchors,
            list(weights),
            use_corpus_nearest=request.use_corpus_nearest,
        )
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))


@app.post("/simplex/prepare_anchors")
def simplex_prepare_anchors(request: SimplexPrepareAnchorsRequest) -> Dict[str, Any]:
    """Compose three diverse anchor blends for a target smell phrase (3 LLM calls)."""
    if not settings.openai_api_key:
        raise HTTPException(status_code=500, detail="OPENAI_API_KEY not configured")
    try:
        config, catalog = _cartridge_context()
        cartridge_status = get_cartridge_status(config)
    except FileNotFoundError as e:
        raise HTTPException(status_code=500, detail=str(e))

    target = request.target.strip()
    corner_specs = [
        ("A", "bright citrus, herbal, or airy facets"),
        ("B", "sweet, gourmand, powdery, or comforting facets"),
        ("C", "woody, resinous, smoky, or dry facets"),
    ]
    anchors: List[Dict[str, Any]] = []
    for token, facet in corner_specs:
        sentence = (
            f"{target} — emphasize {facet}. "
            "This is one corner anchor in a 3-point smell navigation triangle; "
            "make it clearly distinct from the other corners while still evoking the target."
        )
        narrowed = filter_relevant_scents(sentence, catalog, settings.descriptor_filter_top_k)
        result = compose_with_openai(sentence, narrowed, cartridge_status)
        validate_composition(result.scent_sequence, catalog)
        extra = _validate_and_expand(sentence, result.scent_sequence, narrowed, result.justification)
        anchors.append(
            {
                "token": token,
                "label": f"Token {token}",
                "scent_sequence": [item.model_dump() for item in extra["validated_sequence"]],
                "pulse_sequence": [item.model_dump() for item in extra["pulse_sequence"]],
                "justification": extra["justification"],
            }
        )
    return {"target": target, "anchors": anchors}


@app.post("/simplex/prepare_triangle")
def simplex_prepare_triangle(request: SimplexPrepareAnchorsRequest) -> Dict[str, Any]:
    """RAG-informed center + three spread corners pushed from that center."""
    if not settings.openai_api_key:
        raise HTTPException(status_code=500, detail="OPENAI_API_KEY not configured")
    try:
        config, catalog = _cartridge_context()
        cartridge_status = get_cartridge_status(config)
    except FileNotFoundError as e:
        raise HTTPException(status_code=500, detail=str(e))

    try:
        return prepare_triangle(
            request.target,
            catalog,
            cartridge_status,
            corner_mode=request.corner_mode,
            neutral_labels=request.neutral_labels,
        )
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    except Exception as e:
        log.error("prepare_triangle failed for target=%r: %s", request.target, e, exc_info=True)
        raise HTTPException(status_code=422, detail=str(e))


@app.post("/compose", response_model=ComposeResponse)
def compose(request: ComposeRequest) -> ComposeResponse:
    try:
        config, catalog = _cartridge_context()
        cartridge_status = get_cartridge_status(config)
    except FileNotFoundError as e:
        raise HTTPException(status_code=500, detail=str(e))

    if not settings.openai_api_key:
        raise HTTPException(status_code=500, detail="OPENAI_API_KEY not configured")

    try:
        narrowed_catalog = filter_relevant_scents(
            request.sentence, catalog, settings.descriptor_filter_top_k
        )

        # Concrete real-world smells ("strawberry", "sweaty") should compose
        # consistently across runs; abstract requests ("nostalgia") benefit
        # from run-to-run variability, so only concrete requests take the
        # (slower, costlier) self-consistency ensemble path.
        category = "abstract"
        if settings.ensemble_enabled:
            try:
                category = classify_request_with_openai(request.sentence).category
            except Exception as e:
                log.warning("Request classification failed (%s); defaulting to single-shot compose", e)

        if category == "concrete" and settings.ensemble_enabled:
            result = compose_with_ensemble(request.sentence, narrowed_catalog, cartridge_status)
        else:
            result = compose_with_openai(request.sentence, narrowed_catalog, cartridge_status)
        result = result.model_copy(update={"request_category": category})

        validate_composition(result.scent_sequence, narrowed_catalog)
        session_id = new_session_id()
        extra = _validate_and_expand(request.sentence, result.scent_sequence, narrowed_catalog, result.justification)
        output = result.model_copy(update={"session_id": session_id, **extra})
        append_event(
            "compose",
            session_id=session_id,
            human_input=request.sentence,
            request=request.model_dump(),
            response=output.model_dump(),
        )
        return output
    except Exception as e:
        log.error("compose failed for sentence=%r: %s", request.sentence, e, exc_info=True)
        raise HTTPException(status_code=422, detail=str(e))


@app.post("/feedback", response_model=FeedbackResponse)
def feedback(request: FeedbackRequest) -> FeedbackResponse:
    try:
        config, catalog = _cartridge_context()
        cartridge_status = get_cartridge_status(config)
    except FileNotFoundError as e:
        raise HTTPException(status_code=500, detail=str(e))

    if not settings.openai_api_key:
        raise HTTPException(status_code=500, detail="OPENAI_API_KEY not configured")

    try:
        relevance_text = f"{request.original_sentence} {request.latest_feedback}"
        narrowed_catalog = filter_relevant_scents(
            relevance_text, catalog, settings.descriptor_filter_top_k
        )
        # Keep whatever is already in the sequence being revised in scope, even if the
        # re-narrowing for this round wouldn't have picked it -- otherwise a revision could
        # involuntarily drop a scent the user already accepted just because the filter's
        # relevance ranking shifted between rounds.
        current_sequence = (
            request.prior_rounds[-1].resulting_sequence
            if request.prior_rounds
            else request.original_sequence
        )
        for item in current_sequence:
            if item.scent_name in catalog and item.scent_name not in narrowed_catalog:
                narrowed_catalog[item.scent_name] = catalog[item.scent_name]
        result = refine_with_openai(request, narrowed_catalog, cartridge_status)
        validate_composition(result.scent_sequence, narrowed_catalog)
        session_id = request.session_id or new_session_id()
        relevance_sentence = f"{request.original_sentence} {request.latest_feedback}"
        extra = _validate_and_expand(relevance_sentence, result.scent_sequence, narrowed_catalog, result.justification)
        output = result.model_copy(update={"session_id": session_id, **extra})
        append_event(
            "feedback",
            session_id=session_id,
            human_input=request.latest_feedback,
            request=request.model_dump(),
            response=output.model_dump(),
        )
        return output
    except Exception as e:
        log.error("feedback failed for feedback=%r: %s", request.latest_feedback, e, exc_info=True)
        raise HTTPException(status_code=422, detail=str(e))


@app.post("/accept", response_model=AcceptResponse)
def accept(request: AcceptRequest) -> AcceptResponse:
    try:
        record = add_example(
            sentence=request.original_sentence,
            scent_sequence=request.final_sequence,
            feedback_rounds=request.feedback_rounds,
            rating=request.rating,
        )
        session_id = request.session_id or new_session_id()
        output = AcceptResponse(
            example_id=record["id"],
            session_id=session_id,
        )
        append_event(
            "accept",
            session_id=session_id,
            human_input=request.original_sentence,
            request=request.model_dump(),
            response=output.model_dump(),
        )
        return output
    except Exception as e:
        log.error("accept failed for sentence=%r: %s", request.original_sentence, e, exc_info=True)
        raise HTTPException(status_code=422, detail=str(e))


@app.post("/log_interaction", response_model=LogInteractionResponse)
async def log_interaction(request: LogInteractionRequest) -> LogInteractionResponse:
    if not settings.interaction_log_apps_script_url or not settings.interaction_log_token:
        raise HTTPException(status_code=503, detail="Interaction logging is not configured")
    payload = {
        "token": settings.interaction_log_token,
        "target_smell": request.target_smell,
        "aromagen_ratio": request.aromagen_ratio,
        "similarity": request.similarity,
        "feedback": request.feedback,
        "session_id": request.session_id or "",
    }
    # Dual-write: local copy is the fast read-path retrieval index used by
    # compose_with_openai (see interaction_retrieval.py); the Apps Script
    # Sheet below stays the human-facing copy. Local write is best-effort and
    # never blocks/fails this request on its own.
    append_local_log({k: v for k, v in payload.items() if k != "token"})
    try:
        async with httpx.AsyncClient(follow_redirects=True, timeout=30) as client:
            resp = await client.post(settings.interaction_log_apps_script_url, json=payload)
        resp.raise_for_status()
        body = resp.json()
        if body.get("status") != "ok":
            raise ValueError(f"Apps Script returned: {body}")
    except Exception as e:
        log.error("log_interaction failed: %s", e, exc_info=True)
        raise HTTPException(status_code=502, detail=f"Failed to log interaction: {e}")
    return LogInteractionResponse()


@app.post("/transcribe")
async def transcribe(
    audio: UploadFile = File(...),
    session_id: Optional[str] = Form(None),
) -> Dict[str, str]:
    """Transcribe audio using OpenAI Whisper."""
    if not settings.openai_api_key:
        raise HTTPException(status_code=500, detail="OPENAI_API_KEY not configured")
    if not audio.content_type or not audio.content_type.startswith("audio/"):
        raise HTTPException(status_code=400, detail="Expected an audio file")
    try:
        content = await audio.read()
        text = transcribe_audio(content, audio.filename or "audio.webm")
        append_event(
            "transcribe",
            session_id=session_id,
            human_input=text,
            request={"filename": audio.filename, "content_type": audio.content_type},
            response={"text": text},
        )
        return {"text": text}
    except Exception as e:
        log.error("transcribe failed: %s", e, exc_info=True)
        raise HTTPException(status_code=422, detail=str(e))


ALLOWED_IMAGE_TYPES = {
    "image/jpeg",
    "image/png",
    "image/webp",
    "image/gif",
    "image/heic",
    "image/heif",
    "image/jpg",
}


@app.post("/describe_image")
async def describe_image_route(
    image: UploadFile = File(...),
    session_id: Optional[str] = Form(None),
) -> Dict[str, str]:
    """Describe an uploaded image for scent composition."""
    if not settings.openai_api_key:
        raise HTTPException(status_code=500, detail="OPENAI_API_KEY not configured")
    if not image.content_type or image.content_type not in ALLOWED_IMAGE_TYPES:
        raise HTTPException(status_code=400, detail="Expected a JPEG, PNG, WebP, or GIF image")
    try:
        content = await image.read()
        text = describe_image(content, image.content_type)
        append_event(
            "describe_image",
            session_id=session_id,
            human_input=text,
            request={"filename": image.filename, "content_type": image.content_type},
            response={"text": text},
        )
        return {"text": text}
    except Exception as e:
        log.error("describe_image failed: %s", e, exc_info=True)
        raise HTTPException(status_code=422, detail=str(e))
