from __future__ import annotations

from typing import Any, Dict, Optional, Tuple

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware

from .schemas import (
    AcceptRequest,
    AcceptResponse,
    ComposeRequest,
    ComposeResponse,
    FeedbackRequest,
    FeedbackResponse,
)
from .settings import settings
from .openai_client import compose_with_openai, describe_image, refine_with_openai, transcribe_audio
from .conversation_logger import append_event, new_session_id
from .example_bank import add_example
from .cartridge import (
    build_catalog_scents,
    get_cartridge_status,
    load_cartridge_config,
    validate_composition,
)
from .descriptor_filter import filter_relevant_scents


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
        result = compose_with_openai(request.sentence, narrowed_catalog, cartridge_status)
        validate_composition(result.scent_sequence, narrowed_catalog)
        session_id = new_session_id()
        output = result.model_copy(update={"session_id": session_id})
        append_event(
            "compose",
            session_id=session_id,
            human_input=request.sentence,
            request=request.model_dump(),
            response=output.model_dump(),
        )
        return output
    except Exception as e:
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
        output = result.model_copy(update={"session_id": session_id})
        append_event(
            "feedback",
            session_id=session_id,
            human_input=request.latest_feedback,
            request=request.model_dump(),
            response=output.model_dump(),
        )
        return output
    except Exception as e:
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
        raise HTTPException(status_code=422, detail=str(e))
