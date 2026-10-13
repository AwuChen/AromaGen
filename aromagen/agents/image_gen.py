"""Generate a visual scene from a smell request (OpenAI Images API)."""
from __future__ import annotations

import base64
import logging
from typing import Any, Dict, Optional

import httpx
from openai import OpenAI

from .settings import settings

log = logging.getLogger(__name__)

SCENE_IMAGE_PROMPT = (
    "Photorealistic still-life or environment scene that strongly evokes this smell: "
    "{sentence}. Show concrete objects and materials (food, plants, smoke, wood, fabric, "
    "drinks, etc.) — not abstract art. Natural lighting, rich detail, no visible text, "
    "no logos, no watermark, no centered portrait faces."
)


def build_scene_image_prompt(sentence: str) -> str:
    return SCENE_IMAGE_PROMPT.format(sentence=sentence.strip())


def _image_generate_kwargs(prompt: str) -> Dict[str, Any]:
    model = settings.openai_image_model
    kwargs: Dict[str, Any] = {
        "model": model,
        "prompt": prompt,
        "n": 1,
    }
    if settings.openai_image_size:
        kwargs["size"] = settings.openai_image_size
    # Optional quality is only supported on DALL·E 3; newer image models reject it.
    if model == "dall-e-3" and settings.openai_image_quality:
        kwargs["quality"] = settings.openai_image_quality
    return kwargs


def _persist_image_bytes(out_path, data: bytes) -> str:
    out_path.write_bytes(data)
    return f"/generated_images/{out_path.name}"


def generate_scent_scene_image(sentence: str, session_id: str) -> Optional[str]:
    """
    Generate and persist a PNG for this session. Returns a URL path served by
    the API (e.g. /generated_images/{session_id}.png), or None on failure.
    """
    if not settings.image_gen_enabled or not settings.openai_api_key:
        return None

    prompt = build_scene_image_prompt(sentence)
    out_dir = settings.generated_images_dir
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"{session_id}.png"

    try:
        client = OpenAI(api_key=settings.openai_api_key)
        response = client.images.generate(**_image_generate_kwargs(prompt))
        item = response.data[0]
        if getattr(item, "b64_json", None):
            return _persist_image_bytes(
                out_path, base64.standard_b64decode(item.b64_json)
            )
        if getattr(item, "url", None):
            with httpx.Client(follow_redirects=True, timeout=120) as http:
                img_resp = http.get(item.url)
                img_resp.raise_for_status()
            return _persist_image_bytes(out_path, img_resp.content)
        log.warning("Image API returned no url or b64_json for session %s", session_id)
        return None
    except Exception as e:
        log.warning("Scene image generation failed for session %s: %s", session_id, e)
        return None
