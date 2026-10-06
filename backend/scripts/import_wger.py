#!/usr/bin/env python3
"""Bring wger's open exercise data into MetalArm's library: artwork, muscles,
equipment - each piece with its licence and author.

wger (https://wger.de) publishes its exercise database under Creative
Commons, mostly CC-BY-SA. Attribution is a condition of using it, so nothing
leaves this script without `media_license`, `media_author` and
`media_source_url`, and every credit is listed on the app's /about/credits.
Share-alike covers the images as adapted (resized, re-encoded): they stay
CC-BY-SA, and the credits page says so.

Two steps, so the network is touched once and the result is reviewable:

    # 1. Pin a snapshot: wger's API -> app/data/wger/exercises.json (trimmed to
    #    the fields we use, English names only).
    python -m scripts.import_wger snapshot

    # 2. Match the snapshot against app/data/exercises.json and enrich the
    #    library rows it finds: image (downloaded to frontend/assets), secondary
    #    muscles, and the credit. Writes exercises.json in place and prints
    #    what matched and what did not.
    python -m scripts.import_wger enrich --assets ../frontend/assets/exercises

Phase 0 only ENRICHES the existing library. Importing wger's exercises as new
library rows is Phase 3, after a licence review of exactly what is shipped.

Every wger muscle and equipment id is mapped explicitly below; an id missing
from the map fails the run rather than being guessed.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import urllib.request
from pathlib import Path

from app.core import exercise_aliases
from app.core.exercise_names import name_key, slugify

DATA = Path(__file__).resolve().parents[1] / "app" / "data"
SNAPSHOT = DATA / "wger" / "exercises.json"
LIBRARY = DATA / "exercises.json"
API = "https://wger.de/api/v2"
ENGLISH = 2

LICENSES = {1: "CC-BY-SA 3.0", 2: "CC-BY-SA 4.0", 3: "CC0 1.0", 4: "CC-BY 4.0", 5: "ODbL"}
# wger muscle id -> our MuscleGroup code. Brachialis sits under the biceps and
# soleus under the gastrocnemius, which is where a lifter would look for them.
# Serratus anterior has no code of its own; it works with the chest in pushing.
MUSCLES = {
    1: "biceps", 2: "shoulders", 3: "chest", 4: "chest", 5: "triceps", 6: "abs",
    7: "calves", 8: "glutes", 9: "traps", 10: "quads", 11: "hamstrings", 12: "lats",
    13: "biceps", 14: "obliques", 15: "calves",
}
# wger equipment id -> our Equipment code, and which wins when an exercise
# lists several (a barbell bench press lists the barbell AND the bench).
EQUIPMENT = {
    1: "barbell", 2: "ez_bar", 3: "dumbbell", 4: "bodyweight", 5: "other", 6: "bodyweight",
    7: "bodyweight", 8: "other", 9: "other", 10: "kettlebell", 11: "band", 12: "cable",
}
EQUIPMENT_PRIORITY = ["barbell", "ez_bar", "dumbbell", "kettlebell", "cable", "band",
                      "bodyweight", "other"]


# ---------------------------------------------------------------------------
# 1. Snapshot
# ---------------------------------------------------------------------------


def _get(url: str) -> dict:
    request = urllib.request.Request(url, headers={"User-Agent": "MetalArm library import"})
    with urllib.request.urlopen(request, timeout=60) as response:
        return json.load(response)


def snapshot() -> int:
    url = f"{API}/exerciseinfo/?limit=100"
    rows = []
    while url:
        page = _get(url)
        for x in page["results"]:
            english = next((t for t in x["translations"] if t["language"] == ENGLISH), None)
            if english is None:
                continue
            for muscle in x["muscles"] + x["muscles_secondary"]:
                if muscle["id"] not in MUSCLES:
                    raise SystemExit(f"unmapped wger muscle {muscle['id']} {muscle['name']}")
            for item in x["equipment"]:
                if item["id"] not in EQUIPMENT:
                    raise SystemExit(f"unmapped wger equipment {item['id']} {item['name']}")
            image = next((i for i in x["images"] if i["is_main"]), x["images"][0] if x["images"] else None)
            rows.append({
                "id": x["id"],
                "uuid": x["uuid"],
                "name": english["name"].strip(),
                "category": x["category"]["name"],
                "muscles": [m["id"] for m in x["muscles"]],
                "muscles_secondary": [m["id"] for m in x["muscles_secondary"]],
                "equipment": [e["id"] for e in x["equipment"]],
                "license": x["license"]["id"],
                "license_author": x.get("license_author") or "",
                "image": None if image is None else {
                    "url": image["image"],
                    "license": image["license"],
                    "author": image.get("license_author") or "",
                    "ai_generated": bool(image.get("is_ai_generated")),
                },
            })
        url = page["next"]
    SNAPSHOT.parent.mkdir(parents=True, exist_ok=True)
    SNAPSHOT.write_text(json.dumps(rows, indent=1, ensure_ascii=False) + "\n")
    print(f"snapshot: {len(rows)} exercises, {sum(1 for r in rows if r['image'])} with an image")
    return 0


# ---------------------------------------------------------------------------
# 2. Enrich
# ---------------------------------------------------------------------------


def _keys(name: str) -> set[str]:
    """Spellings a name could match under: as written, without a trailing
    equipment qualifier in brackets, and with plurals and hyphens folded."""
    base = name_key(name)
    plain = re.sub(r"\s*\(.*?\)\s*", " ", base).strip()
    out = {base, plain}
    for k in list(out):
        out.add(k.replace("-", " "))
        out.add(re.sub(r"s\b", "", k))
    return {k for k in out if k}


def match(library: list[dict], wger: list[dict]) -> dict[str, dict]:
    """Library slug -> the wger exercise it is, by name or a shipped alias.
    Only exact matches: a wrong picture on a lift is worse than none."""
    by_key: dict[str, list[dict]] = {}
    for w in wger:
        for k in _keys(w["name"]):
            by_key.setdefault(k, []).append(w)
    aliases = exercise_aliases.definitions()
    out = {}
    for row in library:
        names = [row["name"], *aliases.get(row["slug"], ())]
        for name in names:
            hits = [w for k in _keys(name) for w in by_key.get(k, [])]
            # Prefer one with a picture, then the lowest id (wger's oldest,
            # usually the canonical entry).
            hits.sort(key=lambda w: (w["image"] is None, w["id"]))
            if hits:
                out[row["slug"]] = hits[0]
                break
    return out


def credit(w: dict) -> tuple[str, str, str]:
    """(licence, author, source) for one wger exercise's image."""
    image = w["image"]
    author = (image["author"] or w["license_author"] or "").strip() or "wger.de contributors"
    return (
        LICENSES.get(image["license"], LICENSES.get(w["license"], "CC-BY-SA 4.0")),
        author[:200],
        f"https://wger.de/en/exercise/{w['id']}/view/",
    )


def _download(url: str, dest: Path) -> None:
    request = urllib.request.Request(url, headers={"User-Agent": "MetalArm library import"})
    with urllib.request.urlopen(request, timeout=60) as response:
        dest.write_bytes(response.read())


def enrich(assets: Path) -> int:
    wger = json.loads(SNAPSHOT.read_text())
    lines = LIBRARY.read_text().splitlines()
    library = [json.loads(l.rstrip(",")) for l in lines if l.strip().startswith("{")]
    found = match(library, wger)
    assets.mkdir(parents=True, exist_ok=True)

    pictured = 0
    out_lines = []
    for line in lines:
        if not line.strip().startswith("{"):
            out_lines.append(line)
            continue
        trailing = "," if line.rstrip().endswith(",") else ""
        row = json.loads(line.rstrip().rstrip(","))
        w = found.get(row["slug"])
        if w is not None:
            secondary = sorted({MUSCLES[m] for m in w["muscles_secondary"]}
                               - set(row["primary_muscle_groups"]))
            if secondary and not row.get("secondary_muscle_groups"):
                row["secondary_muscle_groups"] = secondary
            image = w["image"]
            if image and not image["ai_generated"]:
                ext = Path(image["url"]).suffix or ".png"
                filename = f"{slugify(row['slug'])}{ext}"
                _download(image["url"], assets / filename)
                license_, author, source = credit(w)
                row.update({
                    "illustration_url": f"/exercises/{filename}",
                    "thumbnail_url": f"/exercises/{filename}",
                    "media_license": license_,
                    "media_author": author,
                    "media_source_url": source,
                })
                pictured += 1
        if "mechanic" not in row:
            tags = set(row.get("tags", []))
            row["mechanic"] = ("isolation" if "isolation" in tags
                               else "compound" if tags & {"compound", "compound_heavy", "compound_light", "big3"}
                               else None)
        out_lines.append("  " + json.dumps(row, ensure_ascii=False) + trailing)
    LIBRARY.write_text("\n".join(out_lines) + "\n")

    missing = [r["name"] for r in library if r["slug"] not in found]
    print(f"matched {len(found)}/{len(library)}; {pictured} now have artwork")
    print("no wger match:", ", ".join(missing) if missing else "none")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    sub = ap.add_subparsers(dest="command", required=True)
    sub.add_parser("snapshot")
    e = sub.add_parser("enrich")
    e.add_argument("--assets", type=Path, required=True)
    args = ap.parse_args()
    return snapshot() if args.command == "snapshot" else enrich(args.assets)


if __name__ == "__main__":
    sys.exit(main())
