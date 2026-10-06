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

    # 3. Add wger exercises the library does not have yet, after a licence
    #    review (allowed licences only, no AI images, a usable English name,
    #    mapped muscles). Appends to exercises.json, downloads and resizes the
    #    images, and writes docs/wger-licence-review.md with what was left out.
    python -m scripts.import_wger library --assets ../frontend/assets/exercises

Every wger muscle and equipment id is mapped explicitly below; an id missing
from the map fails the run rather than being guessed.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
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
                # The how-to text, with the translation's own licence.
                "description": english.get("description") or "",
                "description_license": english.get("license") or x["license"]["id"],
                "description_author": (english.get("license_author") or "").strip(),
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


def _ext(url: str) -> str:
    """The file extension to save under: .jfif is a JPEG, and servers do not
    all know the name."""
    ext = Path(url).suffix.lower() or ".png"
    return ".jpg" if ext in (".jfif", ".jpeg") else ext


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


# ---------------------------------------------------------------------------
# 3. Library: new exercises from wger, after a licence review
# ---------------------------------------------------------------------------

# What may ship: attribution and share-alike are met by the credits page and
# by the adapted images staying under their licence. ODbL (data) and anything
# unknown stay out.
ALLOWED_LICENSES = {1, 2, 3, 4}
NAME_OK = re.compile(r"^[A-Za-z0-9][A-Za-z0-9 ()'/,.&+-]{2,59}$")
REVIEW = Path(__file__).resolve().parents[2] / "docs" / "wger-licence-review.md"
# The hand review: per wger id, "same" (it is a library exercise), "skip"
# (with why), or field overrides. See the file's _note.
DECISIONS = DATA / "wger" / "review.json"
OVERRIDABLE = ("name", "category", "equipment", "primary_muscle_groups", "secondary_muscle_groups")


def text_of(html: str) -> list[str]:
    """wger's description HTML -> steps: list items if any, else paragraphs."""
    items = re.findall(r"<li[^>]*>(.*?)</li>", html, flags=re.S | re.I)
    parts = items or re.split(r"</p>|<br\s*/?>|\n\n", html, flags=re.I)
    out = []
    for part in parts:
        clean = re.sub(r"<[^>]+>", " ", part)
        clean = re.sub(r"\s+", " ", clean.replace("&nbsp;", " ").replace("&amp;", "&")).strip()
        if len(clean) > 2:
            out.append(clean[:400])
    return out[:12]


def candidate(w: dict) -> tuple[dict | None, str]:
    """(library row, "") for a wger exercise that may ship, else (None, why not)."""
    image = w["image"]
    if image is None:
        return None, "no image"
    if image["ai_generated"]:
        return None, "AI-generated image"
    if image["license"] not in ALLOWED_LICENSES or w["license"] not in ALLOWED_LICENSES:
        return None, "licence not on the allow list"
    if w.get("description_license", w["license"]) not in ALLOWED_LICENSES:
        return None, "licence not on the allow list"
    name = re.sub(r"\s+", " ", w["name"]).strip()
    if not NAME_OK.match(name) or name.upper() == name:
        return None, "name not usable as English"
    primary = list(dict.fromkeys(MUSCLES[m] for m in w["muscles"]))
    if not primary and w["category"] != "Cardio":
        return None, "no primary muscles"
    if not primary:
        primary = ["cardio"]
    secondary = sorted({MUSCLES[m] for m in w["muscles_secondary"]} - set(primary))
    kinds = [EQUIPMENT[e] for e in w["equipment"]]
    equipment = next((e for e in EQUIPMENT_PRIORITY if e in kinds), "bodyweight")
    category = "cardio" if w["category"] == "Cardio" else (
        "bodyweight" if equipment == "bodyweight" else "strength")
    license_, author, source = credit(w)
    row = {
        "slug": slugify(name), "name": name, "category": category,
        "primary_muscle_groups": primary, "equipment": equipment, "tags": [],
        "secondary_muscle_groups": secondary, "mechanic": None,
        "steps": text_of(w.get("description") or ""),
        "media_license": license_, "media_author": author, "media_source_url": source,
        "_image": image["url"],
    }
    return row, ""


def library_import(assets: Path, size: int) -> int:
    wger = json.loads(SNAPSHOT.read_text())
    lines = LIBRARY.read_text().splitlines()
    library = [json.loads(l.rstrip().rstrip(",")) for l in lines if l.strip().startswith("{")]
    matched = {w["id"] for w in match(library, wger).values()}
    taken = {k for row in library for k in _keys(row["name"])}
    taken |= {k for names in exercise_aliases.definitions().values() for n in names for k in _keys(n)}
    slugs = {row["slug"] for row in library}

    decisions = {int(k): v for k, v in json.loads(DECISIONS.read_text()).items() if k.isdigit()}
    by_slug = {row["slug"]: row for row in library}
    rows, reasons, same = [], {}, []
    for w in sorted(wger, key=lambda w: w["id"]):
        if w["id"] in matched:
            reasons[w["id"]] = "already in the library"
            continue
        row, why = candidate(w)
        if row is None:
            reasons[w["id"]] = why
            continue
        decision = decisions.get(w["id"], {})
        if "skip" in decision:
            reasons[w["id"]] = "left out in review"
            continue
        if "same" in decision:
            reasons[w["id"]] = "already in the library (matched in review)"
            target = by_slug[decision["same"]]
            # The first twin (lowest wger id) gives the picture; one each.
            if not target.get("illustration_url") and all(t is not target for t, _, _ in same):
                same.append((target, row["_image"], row))
            continue
        for key in OVERRIDABLE:
            if key in decision:
                row[key] = decision[key]
        if decision.get("image") is False:
            # Kept, but not with that picture - nor wger's text, since the
            # credit fields will be the diagram's and CC-BY-SA text needs one.
            # Names and muscles are facts.
            row["_image"] = None
            row["steps"] = []
            for key in ("media_license", "media_author", "media_source_url"):
                row.pop(key, None)
            reasons[f"image-{w['id']}"] = "image left out in review"
        row["slug"] = slugify(row["name"])
        row["secondary_muscle_groups"] = [m for m in row["secondary_muscle_groups"]
                                          if m not in row["primary_muscle_groups"]]
        if not w["equipment"] and "equipment" not in decision:
            # wger has no machine equipment: read it from the name.
            lowered = row["name"].lower()
            if "smith" in lowered:
                row["equipment"], row["category"] = "smith_machine", "strength"
            elif "machine" in lowered:
                row["equipment"], row["category"] = "machine", "strength"
        if _keys(row["name"]) & taken or row["slug"] in slugs:
            reasons[w["id"]] = "duplicate name"
            continue
        taken |= _keys(row["name"])
        slugs.add(row["slug"])
        rows.append((w, row))

    assets.mkdir(parents=True, exist_ok=True)
    # A library exercise without art takes the image of its wger twin.
    enriched = 0
    for target, image_url, row in same:
        filename = f"{target['slug']}{_ext(image_url)}"
        if not (assets / filename).exists():
            _download(image_url, assets / filename)
            subprocess.run(["sips", "-Z", str(size), str(assets / filename)], capture_output=True, check=False)
        target.update({"illustration_url": f"/exercises/{filename}", "thumbnail_url": f"/exercises/{filename}",
                       "media_license": row["media_license"], "media_author": row["media_author"],
                       "media_source_url": row["media_source_url"]})
        enriched += 1
    lines = [("  " + json.dumps(by_slug[json.loads(l.rstrip().rstrip(","))["slug"]], ensure_ascii=False)
              + ("," if l.rstrip().endswith(",") else "")) if l.strip().startswith("{") else l for l in lines]
    out = []
    for w, row in rows:
        image_url = row.pop("_image")
        if image_url is None:
            out.append(row)
            continue
        filename = f"{row['slug']}{_ext(image_url)}"
        dest = assets / filename
        if not dest.exists():
            _download(image_url, dest)
            # Adapted (resized) - still under the image's own licence.
            subprocess.run(["sips", "-Z", str(size), str(dest)], capture_output=True, check=False)
        row["illustration_url"] = row["thumbnail_url"] = f"/exercises/{filename}"
        out.append(row)

    body = [l for l in lines if l.strip() not in ("[", "]")]
    if body and not body[-1].rstrip().endswith(","):
        body[-1] = body[-1].rstrip() + ","
    body += ["  " + json.dumps(r, ensure_ascii=False) + "," for r in out]
    body[-1] = body[-1].rstrip(",")
    LIBRARY.write_text("[\n" + "\n".join(body) + "\n]\n")
    _review(len(wger), out, reasons, enriched)
    print(f"imported {len(out)} wger exercises, gave {enriched} library exercises their wger image; "
          f"review in {REVIEW}")
    return 0


def _review(total: int, rows: list[dict], reasons: dict[int, str], enriched: int) -> None:
    from collections import Counter
    excluded = Counter(reasons.values())
    # Exercises kept without their image are imported, so not "not imported".
    images_left = excluded.pop("image left out in review", 0)
    licences = Counter(r["media_license"] for r in rows if r.get("media_license"))
    lines = [
        "# wger import - licence review",
        "",
        "Written by `backend/scripts/import_wger.py library`. Re-run it to refresh.",
        "",
        f"wger snapshot: **{total}** exercises with an English name. Imported as new library",
        f"exercises: **{len(rows)}**; another **{enriched}** library exercises took the image of",
        "their wger twin. Every one ships with its image, its author and licence, and a link",
        "to its wger page; all are listed on `/about/credits`.",
        "",
        "Every candidate was then read by hand (`backend/app/data/wger/review.json`):",
        "duplicates of library exercises matched instead of added, non-English or unclear",
        "entries left out, and names, muscles, equipment and category corrected where",
        "wger's were wrong.",
        "",
        "## What was allowed",
        "",
        "- Images and descriptions under CC-BY-SA 3.0 / 4.0, CC-BY 4.0 or CC0 1.0.",
        "  Attribution: each exercise stores `media_author`, `media_license` and",
        "  `media_source_url`, shown under the artwork and on the credits page.",
        "- Share-alike: the images are adapted (resized, re-encoded) and stay under",
        "  their original licence; the credits page says so. The descriptions are",
        "  reproduced as steps under the same terms, credited through the same link.",
        "- No AI-generated images (wger flags them).",
        "",
        "## Imported, by image licence",
        "",
        "| Licence | Exercises |",
        "|---|---|",
        *[f"| {k} | {v} |" for k, v in sorted(licences.items())],
        "",
        f"A further **{images_left}** imported exercises keep wger's name and muscles but not its",
        "image or text -",
        "third-party watermarks, logos or copyright notices (which an uploader cannot",
        "licence), or a picture that looks AI-generated though wger does not flag it. They",
        "get MetalArm's own muscle diagram instead.",
        "",
        "## Not imported, by reason",
        "",
        "| Reason | wger exercises |",
        "|---|---|",
        *[f"| {k} | {v} |" for k, v in excluded.most_common()],
        "",
        "Muscles and equipment come through the explicit id maps at the top of the",
        "script; an unmapped id fails the run.",
        "",
    ]
    REVIEW.write_text("\n".join(lines))


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    sub = ap.add_subparsers(dest="command", required=True)
    sub.add_parser("snapshot")
    e = sub.add_parser("enrich")
    e.add_argument("--assets", type=Path, required=True)
    lib = sub.add_parser("library")
    lib.add_argument("--assets", type=Path, required=True)
    lib.add_argument("--size", type=int, default=480, help="Longest side of the shipped image, px.")
    args = ap.parse_args()
    if args.command == "snapshot":
        return snapshot()
    if args.command == "library":
        return library_import(args.assets, args.size)
    return enrich(args.assets)


if __name__ == "__main__":
    sys.exit(main())
