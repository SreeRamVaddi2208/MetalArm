#!/usr/bin/env python3
"""Draw MetalArm's own figures: every exercise without a licensed pose figure
gets the body-map figure (front and back) with its primary muscles lit and its
secondary ones at 40%, plus one tile per muscle group and per equipment type
for Explore.

    frontend/.venv/bin/python scripts/exercise_diagrams.py
    node scripts/e2e/rasterise_figures.mjs <the directory it prints>

Writes SVGs to a build directory (the second step turns them into the PNGs in
frontend/assets, which every client can show; neither native app draws SVG)
and points thumbnail_url / illustration_url at them in
backend/app/data/exercises.json, credited "MetalArm" under CC0 1.0 - our own
drawing (frontend metalarm/ui/body_map.py), so it needs no outside credit.

Exercises with a licensed figure (backend/scripts/import_figures.py, under
/exercises/figures/) are left alone. Where the picture being replaced came from
wger, the how-to text stays: its CC-BY-SA credit moves to text_license and
text_source_url.
"""

from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "frontend"))

from metalarm.ui.body_map import BACK, BASE, FRONT, FRONT_LEGS  # noqa: E402

LIBRARY = ROOT / "backend" / "app" / "data" / "exercises.json"
TAXONOMY = ROOT / "backend" / "app" / "data" / "taxonomy.json"
AUTHOR = "MetalArm"
LICENSE = "CC0 1.0"
PACK_PREFIX = "/exercises/figures/"
SECONDARY = 0.4
# Artwork on the dark UI, on a transparent ground.
FIGURE, REGION, LINE = "#D9D9DD", "#BDBDC3", "#8D8D94"
LIT = "#FF6B2C"
# No region of their own on the map: what these two light up instead.
LEGS = ["quads", "hamstrings", "glutes", "calves"]
WHOLE = ["chest", "back", "lats", "shoulders", "biceps", "triceps", "abs", "obliques", "lower_back", *LEGS]
INDIRECT = {"cardio": LEGS, "full_body": WHOLE}

# Our own simple drawings, on a 100 x 100 grid.
_STEEL, _DARK = 'stroke="#C9C9CE"', 'fill="#3A3A40"'
EQUIPMENT = {
    "barbell": f'<path d="M12 50H88" {_STEEL} stroke-width="4"/><rect x="20" y="28" width="9" height="44" rx="3" {_DARK}/>'
               f'<rect x="71" y="28" width="9" height="44" rx="3" {_DARK}/>',
    "dumbbell": f'<path d="M30 50H70" {_STEEL} stroke-width="7"/><rect x="16" y="32" width="16" height="36" rx="4" {_DARK}/>'
                f'<rect x="68" y="32" width="16" height="36" rx="4" {_DARK}/>',
    "bodyweight": '<circle cx="50" cy="20" r="9" fill="#C9C9CE"/><path d="M50 32V60M30 42H70M50 60L36 86M50 60L64 86" '
                  'stroke="#C9C9CE" stroke-width="7" stroke-linecap="round" fill="none"/>',
    "cable": f'<path d="M26 14V86M74 14V86M20 14H80M20 86H80M50 14V54" {_STEEL} stroke-width="4" fill="none"/>'
             f'<rect x="40" y="54" width="20" height="9" rx="4" {_DARK}/>',
    "machine": f'<path d="M24 86V14H68M24 58H66V86M68 14V36" {_STEEL} stroke-width="5" fill="none"/>'
               f'<rect x="56" y="36" width="24" height="10" rx="4" {_DARK}/><rect x="16" y="50" width="30" height="8" rx="4" {_DARK}/>',
    "smith_machine": f'<path d="M26 12V88M74 12V88M16 42H84" {_STEEL} stroke-width="5"/><rect x="34" y="66" width="32" height="9" rx="4" {_DARK}/>',
    "ez_bar": f'<path d="M10 50H30L40 58L50 44L60 58L70 50H90" {_STEEL} stroke-width="4" fill="none"/>'
              f'<rect x="18" y="32" width="8" height="36" rx="3" {_DARK}/><rect x="74" y="32" width="8" height="36" rx="3" {_DARK}/>',
    "trap_bar": f'<path d="M34 34H66L78 50L66 66H34L22 50ZM8 50H22M78 50H92" {_STEEL} stroke-width="4" fill="none"/>'
                f'<rect x="8" y="34" width="7" height="32" rx="3" {_DARK}/><rect x="85" y="34" width="7" height="32" rx="3" {_DARK}/>',
    "kettlebell": f'<path d="M36 40C30 14 70 14 64 40" {_STEEL} stroke-width="7" fill="none"/><circle cx="50" cy="60" r="25" {_DARK}/>',
    "band": '<path d="M16 34C32 12 42 88 50 66C58 44 68 12 84 40" stroke="#FF6B2C" stroke-width="7" stroke-linecap="round" fill="none"/>',
    "cardio_machine": f'<path d="M14 80L80 62M74 64L70 24H60" {_STEEL} stroke-width="5" fill="none" stroke-linecap="round"/>'
                      f'<path d="M14 88L84 70" stroke="#3A3A40" stroke-width="9" stroke-linecap="round"/>',
    "plate": f'<circle cx="50" cy="50" r="34" {_DARK}/><circle cx="50" cy="50" r="7" fill="#C9C9CE"/>',
    "other": f'<circle cx="50" cy="50" r="30" {_DARK}/><path d="M34 50H66M50 34V66" {_STEEL} stroke-width="5" stroke-linecap="round"/>',
}


def lit_regions(primary: list[str], secondary: list[str], svg_ids: dict[str, list[str]]) -> dict[str, float]:
    def regions(code: str) -> list[str]:
        return [pid for c in INDIRECT.get(code, [code]) for pid in svg_ids.get(c, [])]

    lit: dict[str, float] = {}
    for code in secondary:
        for pid in regions(code):
            lit[pid] = SECONDARY
    for code in primary:
        for pid in regions(code):
            lit[pid] = 1.0
    return lit


def _figure(paths: dict[str, str], extra: list[str], lit: dict[str, float], dx: float) -> str:
    out = [f'<g transform="translate({dx} 25)" stroke="{LINE}" stroke-width=".35">']
    out += [f'<path d="{d}" fill="{FIGURE}"/>' for d in BASE + extra]
    for pid, d in paths.items():
        out.append(f'<path d="{d}" fill="{REGION}"/>')
        if lit.get(pid):
            out.append(f'<path d="{d}" fill="{LIT}" fill-opacity="{lit[pid]}"/>')
    out.append("</g>")
    return "".join(out)


def diagram(name: str, lit: dict[str, float]) -> str:
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 300 300" role="img" '
        f'aria-label="{name}: muscles worked">'
        + _figure(FRONT, list(FRONT_LEGS.values()), lit, 24)
        + _figure(BACK, [], lit, 156)
        + "</svg>"
    )


def _credit_text(row: dict) -> None:
    """The picture is going, wger's words are staying: keep what they owe."""
    if row.get("media_source_url") and (row.get("steps") or row.get("instructions")):
        row["text_license"] = row.get("media_license")
        row["text_source_url"] = row["media_source_url"]


def main() -> int:
    muscles = json.loads(TAXONOMY.read_text())["muscle_groups"]
    svg_ids = {m["code"]: m["svg_path_ids"] for m in muscles}
    build = Path(tempfile.mkdtemp(prefix="metalarm-figures-"))
    for folder in ("exercises/diagrams", "figures/muscles", "figures/equipment"):
        (build / folder).mkdir(parents=True)
    lines = LIBRARY.read_text().splitlines()
    out, made = [], 0
    for line in lines:
        if not line.strip().startswith("{"):
            out.append(line)
            continue
        trailing = "," if line.rstrip().endswith(",") else ""
        row = json.loads(line.rstrip().rstrip(","))
        if not str(row.get("illustration_url") or "").startswith(PACK_PREFIX):
            (build / "exercises/diagrams" / f"{row['slug']}.svg").write_text(diagram(
                row["name"], lit_regions(row["primary_muscle_groups"], row.get("secondary_muscle_groups") or [], svg_ids)))
            _credit_text(row)
            url = f"/exercises/diagrams/{row['slug']}.png"
            row.update({"illustration_url": url, "thumbnail_url": url, "media_license": LICENSE,
                        "media_author": AUTHOR, "media_source_url": None})
            made += 1
        out.append("  " + json.dumps(row, ensure_ascii=False) + trailing)
    LIBRARY.write_text("\n".join(out) + "\n")
    for code in svg_ids:
        (build / "figures/muscles" / f"{code}.svg").write_text(diagram(code, lit_regions([code], [], svg_ids)))
    for code, body in EQUIPMENT.items():
        (build / "figures/equipment" / f"{code}.svg").write_text(
            f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100">{body}</svg>')
    print(f"{made} exercise figures")
    print(build)
    return 0


if __name__ == "__main__":
    sys.exit(main())
