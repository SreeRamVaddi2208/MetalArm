#!/usr/bin/env python3
"""Give every library exercise without artwork MetalArm's own diagram: the
body-map figure (front and back) with the exercise's primary muscles lit and
its secondary ones at 40%, and the equipment named underneath.

    frontend/.venv/bin/python scripts/exercise_diagrams.py

Writes frontend/assets/exercises/diagrams/<slug>.svg and points the exercise's
thumbnail_url / illustration_url at it in backend/app/data/exercises.json,
credited "MetalArm" under CC0 1.0 - it is our own drawing (frontend
metalarm/ui/body_map.py), so it needs no outside credit. Exercises with
licensed artwork (wger) are left alone; re-running regenerates the diagrams.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "frontend"))

from metalarm import theme as t  # noqa: E402
from metalarm.ui.body_map import BACK, BASE, FRONT, FRONT_LEGS  # noqa: E402

LIBRARY = ROOT / "backend" / "app" / "data" / "exercises.json"
TAXONOMY = ROOT / "backend" / "app" / "data" / "taxonomy.json"
OUT = ROOT / "frontend" / "assets" / "exercises" / "diagrams"
AUTHOR = "MetalArm"
LICENSE = "CC0 1.0"
SECONDARY = 0.4
# Light, like the line drawings beside it in a list.
PAPER, FIGURE, REGION, INK = "#F2F2F4", "#D8D8DC", "#C9C9CE", "#6E6E73"


def _figure(paths: dict[str, str], extra: list[str], lit: dict[str, float], dx: float) -> str:
    out = [f'<g transform="translate({dx} 18)">']
    out += [f'<path d="{d}" fill="{FIGURE}"/>' for d in BASE + extra]
    for pid, d in paths.items():
        out.append(f'<path d="{d}" fill="{REGION}"/>')
        if lit.get(pid):
            out.append(f'<path d="{d}" fill="{t.MUSCLE_ACTIVE}" fill-opacity="{lit[pid]}"/>')
    out.append("</g>")
    return "".join(out)


def diagram(name: str, primary: list[str], secondary: list[str], equipment: str,
            svg_ids: dict[str, list[str]]) -> str:
    lit: dict[str, float] = {}
    for code in secondary:
        for pid in svg_ids.get(code, []):
            lit[pid] = SECONDARY
    for code in primary:
        for pid in svg_ids.get(code, []):
            lit[pid] = 1.0
    label = equipment.replace("_", " ").capitalize()
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 300 300" role="img" '
        f'aria-label="{name}: muscles worked">'
        f'<rect width="300" height="300" fill="{PAPER}"/>'
        + _figure(FRONT, list(FRONT_LEGS.values()), lit, 22)
        + _figure(BACK, [], lit, 158)
        + f'<text x="150" y="288" text-anchor="middle" font-family="Inter, system-ui, sans-serif" '
          f'font-size="13" fill="{INK}">{label}</text></svg>'
    )


def main() -> int:
    svg_ids = {m["code"]: m["svg_path_ids"] for m in json.loads(TAXONOMY.read_text())["muscle_groups"]}
    OUT.mkdir(parents=True, exist_ok=True)
    lines = LIBRARY.read_text().splitlines()
    out, made = [], 0
    for line in lines:
        if not line.strip().startswith("{"):
            out.append(line)
            continue
        trailing = "," if line.rstrip().endswith(",") else ""
        row = json.loads(line.rstrip().rstrip(","))
        ours = row.get("media_author") == AUTHOR
        if not row.get("illustration_url") or ours:
            (OUT / f"{row['slug']}.svg").write_text(diagram(
                row["name"], row["primary_muscle_groups"], row.get("secondary_muscle_groups") or [],
                row["equipment"], svg_ids))
            url = f"/exercises/diagrams/{row['slug']}.svg"
            row.update({"illustration_url": url, "thumbnail_url": url, "media_license": LICENSE,
                        "media_author": AUTHOR, "media_source_url": None})
            made += 1
        out.append("  " + json.dumps(row, ensure_ascii=False) + trailing)
    LIBRARY.write_text("\n".join(out) + "\n")
    print(f"{made} diagrams in {OUT.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
