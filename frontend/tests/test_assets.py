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
