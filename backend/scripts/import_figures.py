"""Import a licensed pack of exercise figures.

    python -m scripts.import_figures <pack directory> [--manifest <csv>] [--dry-run]

Run it from backend/ with Pillow available. The manifest (default:
app/data/figures/manifest.csv) has one row per figure:

    slug,file,license,author,source_url

Each figure is squared onto a transparent ground and saved as WebP in
frontend/assets/exercises/figures/, then the exercise in exercises.json is
pointed at it with its credit. An exercise the manifest does not name keeps
MetalArm's own muscle figure. A row without a licence or an author is refused,
like the ck_exercises_media_attribution constraint it would otherwise hit.

Only import a pack whose licence allows bundling it in, and serving it from, a
commercial app. No AI-generated images (docs/wger-licence-review.md).
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
LIBRARY = ROOT / "backend" / "app" / "data" / "exercises.json"
MANIFEST = ROOT / "backend" / "app" / "data" / "figures" / "manifest.csv"
OUT = ROOT / "frontend" / "assets" / "exercises" / "figures"
SIZE = 720


class ManifestError(ValueError):
    pass


def read_manifest(path: Path, known: set[str]) -> list[dict[str, str]]:
    """Every row, or every reason not to import any of them."""
    with path.open(newline="", encoding="utf-8") as fh:
        rows = list(csv.DictReader(fh))
    problems, seen = [], set()
    for number, row in enumerate(rows, start=2):
        slug = (row.get("slug") or "").strip()
        if not (row.get("license") or "").strip() or not (row.get("author") or "").strip():
            problems.append(f"line {number}: {slug or '?'} needs a license and an author")
        if not (row.get("file") or "").strip():
            problems.append(f"line {number}: {slug or '?'} names no file")
        if slug not in known:
            problems.append(f"line {number}: no exercise has the slug {slug!r}")
        if slug in seen:
            problems.append(f"line {number}: {slug} appears twice")
        seen.add(slug)
    if problems:
        raise ManifestError("\n".join(problems))
    return rows


def write_figure(source: Path, dest: Path) -> None:
    from PIL import Image

    with Image.open(source) as image:
        image = image.convert("RGBA")
        image.thumbnail((SIZE, SIZE))
        square = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0))
        square.paste(image, ((SIZE - image.width) // 2, (SIZE - image.height) // 2), image)
        dest.parent.mkdir(parents=True, exist_ok=True)
        square.save(dest, "WEBP", quality=88)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("pack", type=Path)
    parser.add_argument("--manifest", type=Path, default=MANIFEST)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)

    lines = LIBRARY.read_text(encoding="utf-8").splitlines()
    library = {json.loads(l.rstrip().rstrip(","))["slug"]: l for l in lines if l.strip().startswith("{")}
    try:
        rows = read_manifest(args.manifest, set(library))
    except ManifestError as exc:
        print(exc, file=sys.stderr)
        return 1
    missing = [r["file"] for r in rows if not (args.pack / r["file"]).is_file()]
    if missing:
        print("not in the pack:\n" + "\n".join(missing), file=sys.stderr)
        return 1

    by_slug = {r["slug"].strip(): r for r in rows}
    out = []
    for line in lines:
        if not line.strip().startswith("{"):
            out.append(line)
            continue
        trailing = "," if line.rstrip().endswith(",") else ""
        row = json.loads(line.rstrip().rstrip(","))
        figure = by_slug.get(row["slug"])
        if figure is not None:
            url = f"/exercises/figures/{row['slug']}.webp"
            if not args.dry_run:
                write_figure(args.pack / figure["file"], OUT / f"{row['slug']}.webp")
                # The muscle figure this replaces has nothing left using it.
                (OUT.parent / "diagrams" / f"{row['slug']}.png").unlink(missing_ok=True)
            row.update({"illustration_url": url, "thumbnail_url": url,
                        "media_license": figure["license"].strip(), "media_author": figure["author"].strip(),
                        "media_source_url": (figure.get("source_url") or "").strip() or None})
        out.append("  " + json.dumps(row, ensure_ascii=False) + trailing)
    if not args.dry_run:
        LIBRARY.write_text("\n".join(out) + "\n", encoding="utf-8")
    uncovered = sorted(set(library) - set(by_slug))
    print(f"{len(rows)} licensed figures; {len(uncovered)} exercises keep the muscle figure")
    for slug in uncovered:
        print(f"  {slug}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
