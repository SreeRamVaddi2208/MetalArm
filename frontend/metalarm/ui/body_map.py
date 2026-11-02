"""The body map: a front and a back figure, every muscle region a path whose
id matches MuscleGroup.svg_path_ids, filled by intensity.

MetalArm's own drawing - a stylised figure built from smooth outlines, not
traced from any anatomical illustration. Two layers: every
region in a neutral surface tone, then the worked ones again in the
muscle-active colour at an opacity equal to their intensity (0-1).
"""

from __future__ import annotations

from typing import Any

import reflex as rx
from reflex.vars import Var

from metalarm import theme as t


def _ellipse(cx: float, cy: float, rx_: float, ry: float) -> str:
    return (f"M{cx - rx_},{cy} a{rx_},{ry} 0 1,0 {2 * rx_},0 "
            f"a{rx_},{ry} 0 1,0 {-2 * rx_},0 Z")


def _round_rect(x: float, y: float, w: float, h: float, r: float) -> str:
    return (f"M{x + r},{y} h{w - 2 * r} a{r},{r} 0 0 1 {r},{r} v{h - 2 * r} "
            f"a{r},{r} 0 0 1 {-r},{r} h{-(w - 2 * r)} a{r},{r} 0 0 1 {-r},{-r} "
            f"v{-(h - 2 * r)} a{r},{r} 0 0 1 {r},{-r} Z")


def _blob(*points: tuple[float, float]) -> str:
    """A closed, smooth outline through the points (Catmull-Rom as cubics)."""
    n = len(points)
    out = [f"M{points[0][0]},{points[0][1]}"]
    for i in range(n):
        p0, p1, p2, p3 = (points[(i + k) % n] for k in (-1, 0, 1, 2))
        c1 = (p1[0] + (p2[0] - p0[0]) / 6, p1[1] + (p2[1] - p0[1]) / 6)
        c2 = (p2[0] - (p3[0] - p1[0]) / 6, p2[1] - (p3[1] - p1[1]) / 6)
        out.append(f"C{c1[0]:.1f},{c1[1]:.1f} {c2[0]:.1f},{c2[1]:.1f} {p2[0]},{p2[1]}")
    return " ".join(out) + " Z"


def _mirror(points: tuple[tuple[float, float], ...], axis: float = 60) -> tuple[tuple[float, float], ...]:
    return tuple((2 * axis - x, y) for x, y in points)


def _pair(prefix: str, *points: tuple[float, float]) -> dict[str, str]:
    """Left and right copies of one muscle, mirrored about the centre line."""
    return {f"{prefix}-l": _blob(*points), f"{prefix}-r": _blob(*_mirror(points))}


def _both(*points: tuple[float, float]) -> list[str]:
    return [_blob(*points), _blob(*_mirror(points))]


# The silhouette: never lit, shared by both views.
BASE = [
    _ellipse(60, 15, 9, 12),                                                 # head
    _round_rect(53, 22, 14, 14, 4),                                          # neck
    _blob((60, 30), (72, 33), (86, 38), (85, 62), (80, 88), (82, 108), (60, 120),
          (38, 108), (40, 88), (35, 62), (34, 38), (48, 33)),                # torso
    *_both((38, 36), (28, 37), (21, 48), (19, 70), (14, 94), (12, 120), (16, 127),
           (22, 124), (27, 100), (34, 76), (38, 56)),                        # arm
    *_both((13, 122), (11, 133), (14, 143), (20, 140), (23, 128), (20, 121)),  # hand
    *_both((38, 104), (58, 112), (59, 150), (57, 178), (56, 212), (53, 236), (44, 236),
           (40, 212), (36, 178), (34, 146)),                                 # leg
    *_both((44, 233), (53, 233), (54, 244), (47, 247), (38, 246)),           # foot
]

FRONT: dict[str, str] = {
    "front-neck": " ".join(_both((52, 23), (56, 24), (58, 36), (53, 35))),
    **_pair("front-trap", (50, 30), (53, 35), (50, 38), (41, 38), (44, 33)),
    **_pair("front-delt", (37, 38), (29, 38), (22, 48), (22, 60), (30, 57), (36, 48)),
    **_pair("front-chest", (59, 40), (59, 58), (49, 62), (39, 58), (37, 49), (41, 41), (50, 39)),
    **_pair("front-biceps", (31, 56), (24, 62), (21, 76), (24, 85), (29, 80), (33, 67)),
    **_pair("front-forearm", (23, 88), (17, 100), (14, 118), (20, 120), (26, 105), (30, 90), (27, 85)),
    "front-abs": " ".join(_round_rect(x, y, 7.5, h, 2.5) for x in (51.5, 61)
                          for y, h in ((62, 9.5), (72.5, 9.5), (83, 9.5), (93.5, 13))),
    **_pair("front-oblique", (49, 64), (40, 62), (39, 78), (41, 98), (49, 103)),
    **_pair("front-quad", (39, 112), (50, 116), (55, 134), (54, 164), (50, 176), (43, 174), (37, 152)),
    **_pair("front-adductor", (53, 115), (58, 120), (58, 146), (55, 136)),
}

BACK: dict[str, str] = {
    "back-neck": _round_rect(54, 23, 12, 9, 3),
    "back-trap": _blob((60, 31), (70, 35), (79, 39), (68, 50), (60, 66), (52, 50), (41, 39), (50, 35)),
    **_pair("back-delt", (37, 38), (29, 38), (22, 48), (22, 60), (30, 57), (36, 48)),
    "back-upper-back": " ".join(_both((52, 50), (59, 66), (58, 72), (47, 68), (40, 54), (42, 44))),
    **_pair("back-lat", (40, 57), (47, 70), (58, 74), (53, 90), (44, 98), (39, 82), (36, 66)),
    **_pair("back-triceps", (31, 56), (24, 62), (21, 76), (24, 85), (29, 80), (33, 67)),
    **_pair("back-forearm", (23, 88), (17, 100), (14, 118), (20, 120), (26, 105), (30, 90), (27, 85)),
    "back-lower-back": _blob((60, 76), (66, 84), (68, 100), (60, 106), (52, 100), (54, 84)),
    **_pair("back-glute", (59, 108), (59, 128), (48, 133), (39, 126), (38, 112), (47, 103)),
    **_pair("back-abductor", (39, 106), (36, 118), (36, 130), (40, 126), (40, 113)),
    **_pair("back-hamstring", (40, 134), (49, 136), (57, 134), (56, 158), (52, 176), (43, 176), (38, 156)),
    **_pair("back-calf", (42, 182), (50, 180), (55, 190), (54, 208), (50, 226), (46, 226), (41, 208), (39, 192)),
}
# Not a muscle group: the shin, part of the silhouette from the front.
FRONT_LEGS = {"front-shin-l": _blob((42, 184), (50, 182), (54, 196), (52, 226), (46, 226), (41, 200)),
              "front-shin-r": _blob(*_mirror(((42, 184), (50, 182), (54, 196), (52, 226), (46, 226), (41, 200))))}


def _intensity(values: Any, path_id: str) -> Any:
    if isinstance(values, Var):
        # Inside rx.foreach a row's dict arrives untyped; cast it to an object
        # Var so it can be asked what it contains.
        mapping = values.to(dict)
        return rx.cond(mapping.contains(path_id), mapping[path_id], 0)
    return values.get(path_id, 0)


def _figure(paths: dict[str, str], extra_base: list[str], values: Any, size: str) -> rx.Component:
    base = [rx.el.path(d=d, fill=t.SURFACE_2) for d in BASE + extra_base]
    regions = [rx.el.path(d=d, fill=t.BORDER, id=pid) for pid, d in paths.items()]
    lit = [rx.el.path(d=d, fill=t.ACCENT, fill_opacity=_intensity(values, pid))
           for pid, d in paths.items()]
    return rx.el.svg(*base, *regions, *lit, view_box="0 0 120 250", height=size,
                     custom_attrs={"role": "img", "aria-label": "Muscles worked"})


def body_map(values: Any = None, *, views: tuple[str, ...] = ("front", "back"),
             size: str = "220px") -> rx.Component:
    """`values`: {svg_path_id: 0-1}. Build it from a muscle-intensity map with
    `paths_for()`, or pass a Var holding one."""
    values = values if values is not None else {}
    figures = []
    if "front" in views:
        figures.append(_figure(FRONT, list(FRONT_LEGS.values()), values, size))
    if "back" in views:
        figures.append(_figure(BACK, [], values, size))
    return rx.hstack(*figures, spacing="6", justify="center", width="100%")


def paths_for(muscle_values: dict[str, float], svg_ids: dict[str, list[str]]) -> dict[str, float]:
    """{muscle code: intensity} -> {svg path id: intensity}, via the taxonomy's
    svg_path_ids."""
    out: dict[str, float] = {}
    for code, value in muscle_values.items():
        for path_id in svg_ids.get(code, []):
            out[path_id] = max(out.get(path_id, 0.0), round(float(value), 3))
    return out
