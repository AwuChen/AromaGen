"""Center + corner spread for prepare_triangle."""
from __future__ import annotations

from aromagen.agents.simplex import sequence_to_vector
from aromagen.agents.simplex_triangle import (
    _build_corners_from_directions,
    _mix_vectors,
    _min_pairwise_l2,
    _preset_directions,
)
from aromagen.agents.schemas import ScentItem


def test_higher_alpha_increases_spread_from_same_axes():
    odorants = ["A", "B", "C"]
    center = {"A": 0.34, "B": 0.33, "C": 0.33}
    direction = {"A": 0.9, "B": 0.05, "C": 0.05}
    low = _mix_vectors(center, direction, 0.35)
    high = _mix_vectors(center, direction, 0.65)
    assert _min_pairwise_l2([center, low]) < _min_pairwise_l2([center, high])


def test_preset_corners_returns_three_sequences():
    odorants = [
        "Benz Sal",
        "Sandalwood",
        "Clove Bud + Cumin",
        "Lavender + Rose",
        "Orange + Lemon",
        "Vanilla Sugar + Almond Extract",
        "Birch tar oil + Coffee + Clove Bud",
        "Eucalyptus",
        "Cognac",
        "Vinegar",
        "Isovaleric acid",
        "Seaweed + Fenugreek + Garlic",
    ]
    center_seq = [
        ScentItem(scent_name="Lavender + Rose", scent_duration=1.0, ratio=0.5),
        ScentItem(scent_name="Benz Sal", scent_duration=1.0, ratio=0.5),
    ]
    center_vec = sequence_to_vector(center_seq, odorants)
    directions = _preset_directions(odorants)
    a, b, c, alpha, score = _build_corners_from_directions(center_vec, directions, 1.0)
    assert len(a) >= 1 and len(b) >= 1 and len(c) >= 1
    assert score >= 0
