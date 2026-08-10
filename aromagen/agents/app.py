from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional, Tuple

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware

from .schemas import (
    AcceptRequest,
    AcceptResponse,
    ComposeRequest,
    ComposeResponse,
    FeedbackRequest,
    FeedbackResponse,
    ScentItem,
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
def health() -> Dict[str, str]:
    return {"status": "ok"}


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
