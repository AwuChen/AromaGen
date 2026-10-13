"""Generate a visual scene from a smell request (OpenAI Images API)."""
from __future__ import annotations

import base64
import logging
from typing import Optional

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
        response = client.images.generate(
            model=settings.openai_image_model,
            prompt=prompt,
            size=settings.openai_image_size,
            quality=settings.openai_image_quality,
            n=1,
            response_format="b64_json",
        )
        b64 = response.data[0].b64_json
        if not b64:
            log.warning("Image API returned no b64_json for session %s", session_id)
            return None
        out_path.write_bytes(base64.standard_b64decode(b64))
        return f"/generated_images/{session_id}.png"
    except Exception as e:
        log.warning("Scene image generation failed for session %s: %s", session_id, e)
        return None
