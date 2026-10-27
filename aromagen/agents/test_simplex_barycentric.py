"""Corner weights for the simplex triangle (A bottom, B top-left, C top-right)."""
from __future__ import annotations

import math

from aromagen.agents.simplex import barycentric_from_point

H = math.sqrt(3) / 2


def test_corners_map_to_single_anchor():
    ax, ay = 0.5, H
    bx, by = 0.0, 0.0
    cx, cy = 1.0, 0.0

    wa, wb, wc = barycentric_from_point(ax, ay, ax, ay, bx, by, cx, cy)
    assert wa > 0.99 and wb < 0.01 and wc < 0.01

    wa, wb, wc = barycentric_from_point(bx, by, ax, ay, bx, by, cx, cy)
    assert wb > 0.99 and wa < 0.01 and wc < 0.01

    wa, wb, wc = barycentric_from_point(cx, cy, ax, ay, bx, by, cx, cy)
    assert wc > 0.99 and wa < 0.01 and wb < 0.01
