"""Every library exercise's artwork ships with the app (overhaul phase 3
gate): the file each thumbnail_url / illustration_url names is in assets/."""

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
LIBRARY = ROOT / "backend" / "app" / "data" / "exercises.json"
ASSETS = ROOT / "frontend" / "assets"


def test_every_library_image_is_shipped() -> None:
    rows = json.loads(LIBRARY.read_text())
    missing = [(r["slug"], url) for r in rows for url in {r.get("thumbnail_url"), r.get("illustration_url")}
               if not url or not (ASSETS / url.lstrip("/")).is_file()]
    assert missing == []


def test_no_orphan_images() -> None:
    """An image no exercise uses is dead weight (and an unreviewed licence)."""
    used = {Path(r[k]).name for r in json.loads(LIBRARY.read_text())
            for k in ("thumbnail_url", "illustration_url") if r.get(k)}
    on_disk = {p.name for p in (ASSETS / "exercises").rglob("*") if p.is_file()}
    assert on_disk - used == set()


def test_every_exercise_shows_a_figure() -> None:
    """Ours or a licensed pack's: no other picture belongs in the app."""
    for row in json.loads(LIBRARY.read_text()):
        for url in (row["thumbnail_url"], row["illustration_url"]):
            assert url.startswith(("/exercises/diagrams/", "/exercises/figures/")), row["slug"]


def test_every_explore_tile_has_its_picture() -> None:
    taxonomy = json.loads((ROOT / "backend" / "app" / "data" / "taxonomy.json").read_text())
    for kind, key in (("muscles", "muscle_groups"), ("equipment", "equipment")):
        for row in taxonomy[key]:
            if row["browsable"]:
                assert (ASSETS / "figures" / kind / f"{row['code']}.png").is_file(), row["code"]
