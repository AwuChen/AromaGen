from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple, Union

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware

from .schemas import (
    AcceptRequest,
    AcceptResponse,
    CartridgeStateUpdate,
    ComposeRequest,
    ComposeResponse,
    FeedbackRequest,
    FeedbackResponse,
    ScentItem,
)
from .settings import settings
from .openai_client import compose_with_openai, describe_image, refine_with_openai, transcribe_audio
from .conversation_logger import append_event, new_session_id
from .example_bank import add_example
from .cartridge import (
    analyze_swap_requirement,
    build_active_scents,
    build_catalog_scents,
    get_cartridge_status,
    load_cartridge_config,
    load_cartridge_state,
    save_cartridge_state,
)


def _cartridge_context() -> Tuple[Dict[str, Any], Dict[str, str], Dict[str, Dict[str, Any]], Dict[str, Dict[str, Any]]]:
    config = load_cartridge_config(settings.cartridge_sets_path)
    state = load_cartridge_state(settings.cartridge_state_path, config)
    active = build_active_scents(config, state)
    catalog = build_catalog_scents(config, state)
    return config, state, active, catalog


def load_scents() -> Dict[str, Any]:
    """Return the full scent catalog for AI composition (includes unloaded alternate-set scents)."""
    _, _, _, catalog = _cartridge_context()
    return catalog


def _attach_swap_info(
    response: Union[ComposeResponse, FeedbackResponse],
    sequence: List[ScentItem],
) -> Union[ComposeResponse, FeedbackResponse]:
    config, state, _, catalog = _cartridge_context()
    swap = analyze_swap_requirement(sequence, catalog, config, state)
    playable_now = swap is None
    return response.model_copy(update={"cartridge_swap": swap, "playable_now": playable_now})


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
        config, state, active, catalog = _cartridge_context()
    except FileNotFoundError as e:
        raise HTTPException(status_code=500, detail=str(e))

    status = get_cartridge_status(config, state)
    return {
        **status,
        "active_scents": active,
        "catalog_size": len(catalog),
    }


@app.get("/cartridge/active")
def cartridge_active() -> Dict[str, Any]:
    """Scents currently loaded in the device with slot locations (for playback)."""
    try:
        config, state, active, _ = _cartridge_context()
    except FileNotFoundError as e:
        raise HTTPException(status_code=500, detail=str(e))

    return {
        "state": state,
        "status": get_cartridge_status(config, state),
        "scents": active,
    }


@app.put("/cartridge/state")
def update_cartridge_state(update: CartridgeStateUpdate) -> Dict[str, Any]:
    try:
        config = load_cartridge_config(settings.cartridge_sets_path)
        state = save_cartridge_state(
            settings.cartridge_state_path,
            config,
            update.model_dump(),
        )
    except (FileNotFoundError, ValueError) as e:
        raise HTTPException(status_code=400, detail=str(e))

    active = build_active_scents(config, state)
    return {
        "state": state,
        "status": get_cartridge_status(config, state),
        "scents": active,
    }


@app.post("/compose", response_model=ComposeResponse)
def compose(request: ComposeRequest) -> ComposeResponse:
    try:
        config, state, _, catalog = _cartridge_context()
        scents = catalog
        cartridge_status = get_cartridge_status(config, state)
    except FileNotFoundError as e:
        raise HTTPException(status_code=500, detail=str(e))

    if not settings.openai_api_key:
        raise HTTPException(status_code=500, detail="OPENAI_API_KEY not configured")

    try:
        result = compose_with_openai(request.sentence, scents, cartridge_status)
        session_id = new_session_id()
        output = result.model_copy(update={"session_id": session_id})
        output = _attach_swap_info(output, output.scent_sequence)
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
        config, state, _, catalog = _cartridge_context()
        scents = catalog
        cartridge_status = get_cartridge_status(config, state)
    except FileNotFoundError as e:
        raise HTTPException(status_code=500, detail=str(e))

    if not settings.openai_api_key:
        raise HTTPException(status_code=500, detail="OPENAI_API_KEY not configured")

    try:
        result = refine_with_openai(request, scents, cartridge_status)
        session_id = request.session_id or new_session_id()
        output = result.model_copy(update={"session_id": session_id})
        output = _attach_swap_info(output, output.scent_sequence)
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
