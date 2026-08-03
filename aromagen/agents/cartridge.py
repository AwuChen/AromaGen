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


# Full prose (mixing_notes_full, avoid_notes_full) is documentation for humans
# editing cartridge_sets.json -- deliberately excluded from the catalog handed to
# the AI/descriptor filter to avoid a ~3x prompt-size increase (each pair of
# paragraphs runs ~500+ tokens). Only the condensed pairs_well_with/avoid_with
# structured hints reach the model.
_EXCLUDED_FROM_AI_CATALOG = {"mixing_notes_full", "avoid_notes_full"}


def build_catalog_scents(config: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
    """All 12 odorants are permanently loaded across the fixed device slots."""
    catalog: Dict[str, Dict[str, Any]] = {}
    for name, meta in config["odorants"].items():
        entry = {k: v for k, v in meta.items() if k not in _EXCLUDED_FROM_AI_CATALOG}
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


def check_compatibility_warnings(
    sequence: List[ScentItem],
    catalog: Dict[str, Dict[str, Any]],
) -> List[str]:
    """Deterministic, informational-only pairwise check: does the final chosen
    set contain any odorant pair where one is listed in the other's
    avoid_with? Not a hard rule -- the prompt already tells the model
    avoid_with isn't an absolute ban -- this just surfaces what actually got
    chosen despite a flagged clash, without altering the output. No LLM call,
    so it costs nothing to run on every request."""
    names_in_sequence = {item.scent_name for item in sequence}
    warnings: List[str] = []
    seen_pairs = set()
    for item in sequence:
        avoid_list = catalog.get(item.scent_name, {}).get("avoid_with", [])
        for entry in avoid_list:
            other = entry.get("name") if isinstance(entry, dict) else entry
            reason = entry.get("reason", "") if isinstance(entry, dict) else ""
            if other not in names_in_sequence:
                continue
            pair_key = tuple(sorted([item.scent_name, other]))
            if pair_key in seen_pairs:
                continue
            seen_pairs.add(pair_key)
            message = f"{pair_key[0]} + {pair_key[1]}"
            if reason:
                message += f": {reason}"
            warnings.append(message)
    return warnings
