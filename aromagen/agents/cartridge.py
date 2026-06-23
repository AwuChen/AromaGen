from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from .schemas import CartridgeSwapInfo, ScentItem


def _read_json(path: Path) -> Dict[str, Any]:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def _write_json(path: Path, data: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=4)
        f.write("\n")


def load_cartridge_config(sets_path: Path) -> Dict[str, Any]:
    if not sets_path.exists():
        raise FileNotFoundError(f"Cartridge sets JSON not found at {sets_path}")
    return _read_json(sets_path)


def _disabled_sets(config: Dict[str, Any]) -> set[str]:
    return set(config.get("disabled_sets") or [])


def load_cartridge_state(state_path: Path, config: Dict[str, Any]) -> Dict[str, str]:
    if state_path.exists():
        state = _read_json(state_path)
    else:
        state = dict(config.get("default_state", {}))

    left_set = state.get("left_set", "food_left")
    right_set = state.get("right_set", "food_right")
    _validate_state(config, left_set, right_set)
    return {"left_set": left_set, "right_set": right_set}


def save_cartridge_state(state_path: Path, config: Dict[str, Any], state: Dict[str, str]) -> Dict[str, str]:
    left_set = state.get("left_set", "food_left")
    right_set = state.get("right_set", "food_right")
    _validate_state(config, left_set, right_set)
    normalized = {"left_set": left_set, "right_set": right_set}
    _write_json(state_path, normalized)
    return normalized


def _validate_state(config: Dict[str, Any], left_set: str, right_set: str) -> None:
    known_sets = set(config["sets"].keys())
    disabled = _disabled_sets(config)
    if left_set not in known_sets:
        raise ValueError(f"Unknown left_set '{left_set}'. Valid: {sorted(known_sets)}")
    if right_set not in known_sets:
        raise ValueError(f"Unknown right_set '{right_set}'. Valid: {sorted(known_sets)}")
    if left_set in disabled:
        raise ValueError(f"Cartridge set '{left_set}' is temporarily disabled.")
    if right_set in disabled:
        raise ValueError(f"Cartridge set '{right_set}' is temporarily disabled.")
    if left_set == "perfume" and right_set == "perfume":
        raise ValueError("Both halves cannot use the perfume cartridge at once.")



def _slots_for_side(config: Dict[str, Any], side: str) -> List[int]:
    return list(config["sides"][side]["slots"])


def _assign_locations(
    config: Dict[str, Any],
    set_id: str,
    side: str,
) -> Dict[str, Dict[str, Any]]:
    set_def = config["sets"][set_id]
    slots = _slots_for_side(config, side)
    scent_names = list(set_def["scents"].keys())
    if len(scent_names) != len(slots):
        raise ValueError(
            f"Set '{set_id}' has {len(scent_names)} scents but side '{side}' has {len(slots)} slots."
        )

    assigned: Dict[str, Dict[str, Any]] = {}
    for slot, name in zip(slots, scent_names):
        meta = dict(set_def["scents"][name])
        meta["location"] = str(slot)
        meta["set_id"] = set_id
        meta["set_label"] = set_def["label"]
        meta["category"] = set_def.get("category", "unknown")
        meta["side"] = side
        meta["loaded"] = True
        assigned[name] = meta
    return assigned


def build_active_scents(config: Dict[str, Any], state: Dict[str, str]) -> Dict[str, Dict[str, Any]]:
    active: Dict[str, Dict[str, Any]] = {}

    for side_key, set_id in (("left", state["left_set"]), ("right", state["right_set"])):
        active.update(_assign_locations(config, set_id, side_key))

    return active


def build_catalog_scents(config: Dict[str, Any], state: Dict[str, str]) -> Dict[str, Dict[str, Any]]:
    active = build_active_scents(config, state)
    catalog: Dict[str, Dict[str, Any]] = {}

    disabled = _disabled_sets(config)
    for set_id, set_def in config["sets"].items():
        if set_id in disabled:
            continue
        side = set_def["side"]
        if side == "alternate":
            for swap_side in ("left", "right"):
                for name, meta in _assign_locations(config, set_id, swap_side).items():
                    if name in catalog:
                        continue
                    entry = dict(meta)
                    entry["loaded"] = name in active
                    entry["available_on_side"] = swap_side
                    catalog[name] = entry
        else:
            for name, meta in set_def["scents"].items():
                active_meta = active.get(name)
                entry = dict(meta)
                entry["set_id"] = set_id
                entry["set_label"] = set_def["label"]
                entry["category"] = set_def.get("category", "unknown")
                entry["side"] = side
                if active_meta:
                    entry["location"] = active_meta["location"]
                    entry["loaded"] = True
                else:
                    slots = _slots_for_side(config, side)
                    idx = list(set_def["scents"].keys()).index(name)
                    entry["location"] = str(slots[idx])
                    entry["loaded"] = False
                catalog[name] = entry

    return catalog


def get_cartridge_status(config: Dict[str, Any], state: Dict[str, str]) -> Dict[str, Any]:
    sets = config["sets"]
    left = state["left_set"]
    right = state["right_set"]
    perfume_side: Optional[str] = None
    if left == "perfume":
        perfume_side = "left"
    elif right == "perfume":
        perfume_side = "right"

    disabled = sorted(_disabled_sets(config))
    return {
        "left_set": left,
        "right_set": right,
        "left_label": sets[left]["label"],
        "right_label": sets[right]["label"],
        "perfume_cartridge_available": True,
        "perfume_loaded_on": perfume_side,
        "food_loaded_on": {
            "left": left.startswith("food"),
            "right": right.startswith("food"),
        },
        "disabled_sets": disabled,
    }


def analyze_swap_requirement(
    sequence: List[ScentItem],
    catalog: Dict[str, Dict[str, Any]],
    config: Dict[str, Any],
    state: Dict[str, str],
) -> Optional[CartridgeSwapInfo]:
    missing: List[str] = []
    sides_needed: set[str] = set()

    for item in sequence:
        meta = catalog.get(item.scent_name)
        if meta is None:
            continue
        if meta.get("loaded"):
            continue
        missing.append(item.scent_name)
        side = meta.get("available_on_side") or meta.get("side")
        if side in ("left", "right"):
            sides_needed.add(side)

    if not missing:
        return None

    side_to_swap = _choose_swap_side(missing, catalog, config, state, sides_needed)
    food_side = "right" if side_to_swap == "left" else "left"
    current_set = state[f"{side_to_swap}_set"]
    current_label = config["sets"][current_set]["label"]
    perfume_label = config["sets"]["perfume"]["label"]

    if current_set == "perfume":
        swap_to = f"food_{side_to_swap}"
        if swap_to in _disabled_sets(config):
            return None
        instruction = (
            f"Swap the {side_to_swap.upper()} cartridge half back to the food set "
            f"({config['sets'][swap_to]['label']}) to play: "
            f"{', '.join(missing)}."
        )
    else:
        instruction = (
            f"Swap the {side_to_swap.upper()} cartridge half ({current_label}) with the "
            f"perfume cartridge ({perfume_label}) to play: {', '.join(missing)}. "
            f"The {food_side.upper()} half can stay as-is."
        )
        swap_to = "perfume"

    if swap_to in _disabled_sets(config):
        return None

    return CartridgeSwapInfo(
        required=True,
        side_to_swap=side_to_swap,
        swap_to_set=swap_to,
        missing_scents=missing,
        instruction=instruction,
    )


def _choose_swap_side(
    missing: List[str],
    catalog: Dict[str, Dict[str, Any]],
    config: Dict[str, Any],
    state: Dict[str, str],
    sides_needed: set[str],
) -> str:
    if len(sides_needed) == 1:
        return next(iter(sides_needed))

    missing_perfume = [
        name for name in missing if catalog[name].get("set_id") == "perfume"
    ]
    if missing_perfume:
        if state["left_set"] != "perfume":
            return "left"
        return "right"

    for side in ("left", "right"):
        set_id = state[f"{side}_set"]
        set_names = set(config["sets"][set_id]["scents"].keys())
        if any(name in set_names for name in missing):
            return side

    return "left"


def partition_sequence(
    sequence: List[ScentItem],
    catalog: Dict[str, Dict[str, Any]],
) -> Tuple[List[ScentItem], List[ScentItem]]:
    playable: List[ScentItem] = []
    blocked: List[ScentItem] = []
    for item in sequence:
        meta = catalog.get(item.scent_name)
        if meta and meta.get("loaded"):
            playable.append(item)
        else:
            blocked.append(item)
    return playable, blocked
