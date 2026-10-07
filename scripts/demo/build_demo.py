#!/usr/bin/env python3
"""Cut the demo film: title card, the web tour, the iPhone tour, end card -
each tour captioned and narrated chapter by chapter.

    python3 scripts/demo/build_demo.py --assets A --web-dir W --ios-dir I --out O

Inputs:
  A  scripts/demo/render_assets.mjs output: <part>/<id>.aiff voice clips,
     <part>/<id>.png caption strips (1920x120), title.png, end.png.
  W  scripts/e2e/web_tour.mjs output: web-raw.webm + web-marks.json
     ({chapter id: seconds into the recording}).
  I  scripts/record_tour.sh output: metalarm-tour.mp4 + chapters.md (mm:ss
     per chapter title, already measured from the trimmed start).

Frame: 1920x1080. The app is scaled into the top 960 pixels on MetalArm's
background, and the caption owns the 120-pixel band beneath it - so a
caption never covers what it describes. Standard library only; everything
heavy is ffmpeg (Homebrew's build: no drawtext, hence PNG captions).
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import tempfile
from pathlib import Path

W, H, CONTENT_H = 1920, 1080, 960
BG = "0x0b0b0c"
FPS = 30
CARD_SECONDS = 4.0
FADE = 0.5
ENCODE = ["-c:v", "libx264", "-preset", "medium", "-crf", "18", "-pix_fmt", "yuv420p",
          "-r", str(FPS), "-c:a", "aac", "-b:a", "160k", "-ar", "48000", "-ac", "2"]

# record_tour.sh's chapter titles, back to the DemoTour mark ids.
IOS_TITLES = {
    "Onboarding": "onboarding", "Creating an account": "signup",
    "Training path: pick how you train": "trainingpath", "Home: level, tier, streak, trial": "home",
    "Ready-made workouts": "presets", "A demo of every movement": "demo",
    "Starting a workout": "workout", "What to try next": "hint",
    "Logging a set: a personal record": "logset", "Level up": "levelup",
    "Finishing: the summary": "finish", "The share card": "share",
    "Progress: history and records": "progress", "Ranks: league and raid": "ranks",
    "Character sheet and training path": "character", "Rank trials": "trials",
    "Settings: import, reminders, Health": "extras",
    "Rank up: one more workout, then the promotion": "rankup", "End": "end",
}


def run(args: list[str]) -> None:
    subprocess.run(["ffmpeg", "-v", "error", "-y", *args], check=True)


def duration(path: Path) -> float:
    out = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration",
                          "-of", "csv=p=0", str(path)], capture_output=True, text=True, check=True)
    return float(out.stdout.strip())


def ios_marks(chapters_md: Path) -> dict[str, float]:
    marks: dict[str, float] = {}
    for line in chapters_md.read_text().splitlines():
        m = re.match(r"\|\s*(\d+):(\d+)\s*\|\s*(.+?)\s*\|", line)
        if m and m.group(3) in IOS_TITLES:
            marks[IOS_TITLES[m.group(3)]] = int(m.group(1)) * 60 + int(m.group(2))
    return marks


def segments(order: list[str], marks: dict[str, float], start: float, end: float):
    """[(id, from, to)] in seconds relative to `start`, in narration order."""
    present = [(cid, marks[cid]) for cid in order if cid in marks]
    out = []
    for i, (cid, at) in enumerate(present):
        until = present[i + 1][1] if i + 1 < len(present) else end
        out.append((cid, max(0.0, at - start), max(0.0, until - start)))
    return out


def build_part(name: str, video: Path, marks: dict[str, float], order: list[str],
               assets: Path, work: Path, *, fit_voice: bool) -> tuple[Path, list]:
    """One tour, captioned and narrated, as a 1920x1080 mp4."""
    total = duration(video)
    first = min(marks[c] for c in order if c in marks)
    start = max(0.0, first - 0.3)
    length = total - start
    segs = [s for s in segments(order, marks, start, total) if s[2] - s[1] > 0.2]

    inputs = ["-ss", f"{start:.3f}", "-t", f"{length:.3f}", "-i", str(video)]
    for cid, _, _ in segs:
        inputs += ["-i", str(assets / name / f"{cid}.png")]
    for cid, _, _ in segs:
        inputs += ["-i", str(assets / name / f"{cid}.aiff")]

    n = len(segs)
    graph = [
        f"[0:v]fps={FPS},scale={W}:{CONTENT_H}:force_original_aspect_ratio=decrease,"
        f"pad={W}:{H}:(ow-iw)/2:0:color={BG},setsar=1[base0]"
    ]
    for i, (cid, a, b) in enumerate(segs):
        graph.append(
            f"[base{i}][{1 + i}:v]overlay=0:{CONTENT_H}:enable='between(t,{a:.3f},{b:.3f})'[base{i + 1}]"
        )
    voices = []
    for i, (cid, a, b) in enumerate(segs):
        clip = duration(assets / name / f"{cid}.aiff")
        room = max(0.5, b - a - 0.25)
        chain = f"[{1 + n + i}:a]aresample=48000,aformat=channel_layouts=stereo"
        if fit_voice and clip > room:
            # The iPhone tour has fixed pacing: speed the line up a little to
            # fit its chapter, and only then trim what is left over.
            tempo = min(1.25, clip / room)
            chain += f",atempo={tempo:.3f}"
            chain += f",atrim=0:{room:.3f},afade=t=out:st={max(0, room - 0.3):.3f}:d=0.3"
        delay = int(a * 1000) + 150
        chain += f",adelay={delay}|{delay}[v{i}]"
        graph.append(chain)
        voices.append(f"[v{i}]")
    graph.append(f"{''.join(voices)}amix=inputs={n}:normalize=0:dropout_transition=0,"
                 f"apad,atrim=0:{length:.3f},loudnorm=I=-16:TP=-1.5[aout]")
    graph.append(f"[base{n}]fade=t=in:st=0:d={FADE},fade=t=out:st={length - FADE:.3f}:d={FADE}[vout]")

    out = work / f"{name}.mp4"
    script = work / f"{name}.filter"
    script.write_text(";\n".join(graph))
    run([*inputs, "-filter_complex_script", str(script), "-map", "[vout]", "-map", "[aout]",
         "-t", f"{length:.3f}", *ENCODE, str(out)])
    return out, segs


def card(png: Path, out: Path) -> Path:
    run(["-loop", "1", "-t", str(CARD_SECONDS), "-i", str(png),
         "-f", "lavfi", "-t", str(CARD_SECONDS), "-i", "anullsrc=r=48000:cl=stereo",
         "-vf", f"scale={W}:{H},fade=t=in:st=0:d={FADE},fade=t=out:st={CARD_SECONDS - FADE}:d={FADE}",
         "-shortest", *ENCODE, str(out)])
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--assets", type=Path, required=True)
    ap.add_argument("--web-dir", type=Path, required=True)
    ap.add_argument("--ios-dir", type=Path)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--narration", type=Path, default=Path(__file__).parent / "narration.json",
                    help="The script the assets were rendered from.")
    ap.add_argument("--name", default="metalarm-demo", help="File name of the finished film, without .mp4.")
    args = ap.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)
    narration = json.loads(args.narration.read_text())
    titles = {part: {c["id"]: c["caption"] for c in narration[part]} for part in narration
              if isinstance(narration[part], list)}

    with tempfile.TemporaryDirectory() as tmp:
        work = Path(tmp)
        pieces: list[tuple[str, Path, list]] = [("title", card(args.assets / "title.png", work / "title.mp4"), [])]

        web_marks = json.loads((args.web_dir / "web-marks.json").read_text())
        web, web_segs = build_part("web", args.web_dir / "web-raw.webm", web_marks,
                                   [c["id"] for c in narration["web"]], args.assets, work,
                                   fit_voice=False)
        shutil.copy(web, args.out / "metalarm-web.mp4")
        pieces.append(("web", web, web_segs))

        if args.ios_dir and (args.ios_dir / "metalarm-tour.mp4").exists():
            ios, ios_segs = build_part("ios", args.ios_dir / "metalarm-tour.mp4",
                                       ios_marks(args.ios_dir / "chapters.md"),
                                       [c["id"] for c in narration["ios"]], args.assets, work,
                                       fit_voice=True)
            shutil.copy(ios, args.out / "metalarm-ios.mp4")
            pieces.append(("ios", ios, ios_segs))

        pieces.append(("end", card(args.assets / "end.png", work / "end.mp4"), []))

        listing = work / "concat.txt"
        listing.write_text("".join(f"file '{p}'\n" for _, p, _ in pieces))
        film = args.out / f"{args.name}.mp4"
        run(["-f", "concat", "-safe", "0", "-i", str(listing), "-c", "copy",
             "-movflags", "+faststart", str(film)])

        lines = ["# MetalArm - full demo", "", f"`{film}`  ·  {duration(film):.0f}s", "",
                 "| Time | Part | Chapter |", "|---|---|---|"]
        offset = 0.0
        for part, path, segs in pieces:
            if part in ("title", "end"):
                lines.append(f"| {int(offset)//60:02d}:{int(offset)%60:02d} | - | "
                             f"{'Title' if part == 'title' else 'End card'} |")
            for cid, a, _ in segs:
                at = offset + a
                lines.append(f"| {int(at)//60:02d}:{int(at)%60:02d} | "
                             f"{'Web' if part == 'web' else 'iPhone'} | {titles[part][cid]} |")
            offset += duration(path)
        (args.out / "chapters.md").write_text("\n".join(lines) + "\n")
    print(f"wrote {film}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
