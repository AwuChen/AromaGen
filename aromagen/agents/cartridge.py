from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List

from .schemas import ScentItem


def _read_json(path: Path) -> Dict[str, Any]:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def load_cartridge_config(sets_path: Path) -> Dict[str, Any]:
    if not sets_path.exists():
        raise FileNotFoundError(f"Cartridge sets JSON not found at {sets_path}")
    return _read_json(sets_path)


def build_catalog_scents(config: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
    """All 12 odorants are permanently loaded across the fixed device slots."""
    catalog: Dict[str, Dict[str, Any]] = {}
    for name, meta in config["odorants"].items():
        entry = dict(meta)
        entry["loaded"] = True
        catalog[name] = entry
    return catalog


def get_cartridge_status(config: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "odorant_count": len(config["odorants"]),
        "fixed_palette": True,
    }


def validate_composition(
    sequence: List[ScentItem],
    catalog: Dict[str, Dict[str, Any]],
) -> None:
    """Defense-in-depth: confirm every scent name the model returned is one of
    the 12 loaded odorants. The structured-output schema already constrains
    this at the API boundary, but the json_schema fallback path doesn't get
    the same Pydantic-native enum enforcement, so re-check here.
    """
    invalid = [item.scent_name for item in sequence if item.scent_name not in catalog]
    if invalid:
        raise ValueError(
            f"Composition referenced scent name(s) not in the device catalog: {invalid}"
        )
