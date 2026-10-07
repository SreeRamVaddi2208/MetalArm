"""The body map: a front and a back figure, every muscle region a path whose
id matches MuscleGroup.svg_path_ids, filled by intensity.

MetalArm's own drawing - a deliberately simple, geometric figure built from
rounded shapes, not traced from any anatomical illustration. Two layers: every
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


def _pair(prefix: str, shape, left: tuple, mirror_x: float = 60) -> dict[str, str]:
    """Left and right copies of one region, mirrored about the centre line."""
    lx, *rest = left
    if shape is _ellipse:
        cx, cy, a, b = left
        return {f"{prefix}-l": _ellipse(cx, cy, a, b), f"{prefix}-r": _ellipse(2 * mirror_x - cx, cy, a, b)}
    x, y, w, h, r = left
    return {f"{prefix}-l": _round_rect(x, y, w, h, r),
            f"{prefix}-r": _round_rect(2 * mirror_x - x - w, y, w, h, r)}


# The silhouette: head, hands, knees and feet - never lit.
BASE = [
    _ellipse(60, 16, 11, 13),                              # head
    _ellipse(25, 132, 5, 7), _ellipse(95, 132, 5, 7),      # hands
    _round_rect(41, 228, 15, 20, 6), _round_rect(64, 228, 15, 20, 6),  # feet/shins
]

FRONT: dict[str, str] = {
    "front-neck": _round_rect(54, 27, 12, 10, 4),
    **_pair("front-trap", _round_rect, (45, 34, 10, 6, 3)),
    **_pair("front-delt", _ellipse, (33, 47, 9, 9)),
    **_pair("front-chest", _round_rect, (40, 40, 19, 22, 8)),
    **_pair("front-biceps", _round_rect, (24, 58, 10, 26, 5)),
    **_pair("front-forearm", _round_rect, (21, 88, 9, 36, 4.5)),
    "front-abs": _round_rect(50, 64, 20, 38, 6),
    **_pair("front-oblique", _round_rect, (40, 66, 9, 32, 4.5)),
    **_pair("front-quad", _round_rect, (40, 112, 18, 56, 8)),
    **_pair("front-adductor", _round_rect, (53, 112, 6, 34, 3)),
}

BACK: dict[str, str] = {
    "back-neck": _round_rect(54, 27, 12, 10, 4),
    "back-trap": "M42,38 L60,30 L78,38 L70,58 L60,62 L50,58 Z",
    **_pair("back-delt", _ellipse, (33, 47, 9, 9)),
    "back-upper-back": _round_rect(48, 50, 24, 18, 6),
    **_pair("back-lat", _round_rect, (38, 54, 10, 34, 5)),
    **_pair("back-triceps", _round_rect, (24, 58, 10, 26, 5)),
    **_pair("back-forearm", _round_rect, (21, 88, 9, 36, 4.5)),
    "back-lower-back": _round_rect(50, 74, 20, 26, 6),
    **_pair("back-glute", _round_rect, (40, 102, 19, 22, 9)),
    **_pair("back-abductor", _round_rect, (36, 104, 5, 16, 2.5)),
    **_pair("back-hamstring", _round_rect, (41, 128, 17, 44, 7)),
    **_pair("back-calf", _round_rect, (42, 178, 14, 46, 7)),
}
FRONT_LEGS = {**_pair("front-shin", _round_rect, (42, 172, 14, 54, 7))}  # not a muscle group: silhouette


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
