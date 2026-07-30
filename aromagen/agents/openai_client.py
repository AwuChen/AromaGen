from __future__ import annotations

import base64
import io
import json
import logging
from typing import Any, Dict, List, Optional, Type, TypeVar

from jinja2 import Environment, FileSystemLoader, select_autoescape
from openai import OpenAI
from pydantic import BaseModel

from .schemas import ComposeResponse, FeedbackRequest, FeedbackResponse, ScentItem
from .settings import settings
from .example_bank import find_similar

log = logging.getLogger(__name__)

T = TypeVar("T", bound=BaseModel)


def expand_to_pulse_sequence(
    scent_sequence: List[ScentItem],
    pulse_seconds: float,
    rounds: int,
) -> List[ScentItem]:
    """Deterministically turn the model's conceptual scent pick into an
    interleaved pulse train: every distinct odorant in scent_sequence (in
    first-appearance order) fires for pulse_seconds seconds, once per round,
    for `rounds` rounds -- e.g. [A, B, C] -> A B C A B C A B C A B C A B C.

    The model's own per-scent durations are intentionally discarded here;
    this is a hardware-delivery experiment (rapid alternation to encourage
    perceptual blending) separate from the model's compositional reasoning,
    so it's implemented as a deterministic post-processing step rather than
    asked of the model in the prompt.
    """
    seen: List[str] = []
    for item in scent_sequence:
        if item.scent_name not in seen:
            seen.append(item.scent_name)

    return [
        ScentItem(scent_name=name, scent_duration=pulse_seconds)
        for _ in range(rounds)
        for name in seen
    ]


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
    return template.render(
        scents_json=scents_json,
        cartridge_status_json=cartridge_status_json,
        learned_examples=learned_examples or [],
        learned_examples_json=learned_examples_json,
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
                },
                "required": ["scent_name", "scent_duration"],
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
) -> T:
    try:
        return _chat_parse(
            client,
            system_prompt=system_prompt,
            user_message=user_message,
            response_model=response_model,
            max_completion_tokens=max_completion_tokens,
        )
    except Exception as primary_err:
        log.warning(
            "chat.completions.parse failed (%s), trying json_schema fallback",
            primary_err,
        )
        try:
            return _chat_json_schema_fallback(
                client,
                system_prompt=system_prompt,
                user_message=user_message,
                response_model=response_model,
                schema=schema,
                schema_name=schema_name,
                max_completion_tokens=max_completion_tokens,
            )
        except Exception as fallback_err:
            raise RuntimeError(
                f"Structured completion failed: {primary_err}; fallback: {fallback_err}"
            ) from fallback_err


def compose_with_openai(
    sentence: str,
    scents: Dict[str, Any],
    cartridge_status: Optional[Dict[str, Any]] = None,
) -> ComposeResponse:
    learned_examples = find_similar(sentence)
    system_prompt = _render_prompt(
        "system_prompt.j2",
        scents,
        cartridge_status,
        learned_examples=learned_examples,
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
