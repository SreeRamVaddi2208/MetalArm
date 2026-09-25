#!/usr/bin/env bash
# Records the DemoTour on a throwaway iPhone 17 Pro Max and writes a chapter list.
#
#   scripts/record_tour.sh [destination-folder]
#
# The tour (ios/MetalARMUITests/DemoTour.swift) prints "DEMO_MARK <name> <unix
# time>" as it walks the app; subtracting the moment recording started turns
# those into offsets into the video, so the chapters land on real frames
# instead of guessed pacing.
#
# Everything here was learned the hard way, so leave it alone unless it breaks:
#   - a FRESH simulator, so no leftover state (a signed-in account, a half
#     finished workout) shows up on camera;
#   - the status bar pinned to 9:41 with full battery and signal, or the clock
#     drifts mid-take and the notch reads differently in every chapter;
#   - build-for-testing BEFORE recording starts, so compilation is not in the
#     video;
#   - kill -INT, never plain kill: the recorder has to finalise the container
#     or the file is unplayable;
#   - -parallel-testing-enabled NO, or xcodebuild clones simulators, records
#     the wrong one, and the capture is of an idle home screen.
set -u

DEST="${1:-$HOME/Desktop/MetalArm Recordings/$(date +%Y-%m-%d)}"
mkdir -p "$DEST"
OUT="$DEST/metalarm-tour.mp4"
CHAPTERS="$DEST/chapters.md"
WORK=$(mktemp -d)
trap 'rm -rf "$WORK"' EXIT

cd "$(dirname "${BASH_SOURCE[0]}")/../ios" || exit 1

UDID=$(xcrun simctl create "Tour iPhone 17 Pro Max" "iPhone 17 Pro Max" com.apple.CoreSimulator.SimRuntime.iOS-26-5)
[ -n "$UDID" ] || { echo "Could not create the simulator" >&2; exit 1; }
echo "simulator: $UDID"
xcrun simctl boot "$UDID"
xcrun simctl bootstatus "$UDID" -b >/dev/null
xcrun simctl status_bar "$UDID" override --time "9:41" --batteryState charged \
  --batteryLevel 100 --cellularBars 4 --wifiBars 3 2>/dev/null

echo "building..."
xcodebuild build-for-testing -project MetalARM.xcodeproj -scheme MetalARM \
  -destination "platform=iOS Simulator,id=$UDID" -derivedDataPath "$WORK/dd" \
  > "$WORK/build.log" 2>&1 || {
    echo "BUILD FAILED"; grep -E "error:" "$WORK/build.log" | head -5
    xcrun simctl delete "$UDID" >/dev/null 2>&1; exit 1; }

rm -f "$OUT"
START=$(python3 -c 'import time; print(time.time())')
xcrun simctl io "$UDID" recordVideo --codec h264 --mask ignored "$OUT" &
REC=$!
sleep 2

echo "touring..."
xcodebuild test-without-building -project MetalARM.xcodeproj -scheme MetalARM \
  -destination "platform=iOS Simulator,id=$UDID" -parallel-testing-enabled NO \
  -only-testing:MetalARMUITests/DemoTour -derivedDataPath "$WORK/dd" \
  > "$WORK/run.log" 2>&1
RC=$?

kill -INT $REC 2>/dev/null
wait $REC 2>/dev/null
sleep 3

echo "tour rc=$RC"
MARKS=$(grep -c "DEMO_MARK" "$WORK/run.log")
echo "marks: $MARKS  (19 means every chapter fired)"
cp "$WORK/run.log" "$DEST/tour-run.log"

# The first half-minute is the runner installing the app: trim to just before
# the tour's first mark, so the video opens on the app and not a blank screen.
FIRST=$(grep -o "DEMO_MARK [a-z]* [0-9.]*" "$WORK/run.log" | head -1 | awk '{print $3}')
if [ -n "$FIRST" ]; then
  LEAD=$(python3 -c "print(max(0, $FIRST - $START - 3))")
  ffmpeg -v error -y -ss "$LEAD" -i "$OUT" -c copy "$WORK/trimmed.mp4" && mv "$WORK/trimmed.mp4" "$OUT"
  START=$(python3 -c "print($START + $LEAD)")
fi

python3 - "$START" "$WORK/run.log" "$CHAPTERS" "$OUT" <<'PY'
import re, subprocess, sys
start, log, out_md, video = float(sys.argv[1]), sys.argv[2], sys.argv[3], sys.argv[4]
titles = {
    "onboarding": "Onboarding", "signup": "Creating an account",
    "trainingpath": "Training path: pick how you train", "home": "Home: level, tier, streak, trial",
    "presets": "Ready-made workouts", "demo": "A demo of every movement",
    "workout": "Starting a workout", "hint": "What to try next",
    "logset": "Logging a set: a personal record", "levelup": "Level up",
    "finish": "Finishing: the summary", "share": "The share card",
    "progress": "Progress: history and records", "ranks": "Ranks: league and raid",
    "character": "Character sheet and training path", "trials": "Rank trials",
    "extras": "Settings: import, reminders, Health", "rankup": "Rank up: one more workout, then the promotion",
    "end": "End",
}
marks = []
for line in open(log, errors="ignore"):
    m = re.search(r"DEMO_MARK (\w+) ([0-9.]+)", line)
    if m and (not marks or marks[-1][0] != m.group(1)):
        marks.append((m.group(1), float(m.group(2))))
dur = subprocess.run(["ffprobe","-v","error","-show_entries","format=duration","-of","csv=p=0",video],
                     capture_output=True, text=True).stdout.strip()
lines = [f"# MetalArm - recorded tour\n", f"`{video}`  ·  {float(dur or 0):.0f}s\n", "| Time | Chapter |", "|---|---|"]
for name, ts in marks:
    off = max(0, ts - start)  # measured from the trimmed start
    lines.append(f"| {int(off)//60:02d}:{int(off)%60:02d} | {titles.get(name, name)} |")
open(out_md, "w").write("\n".join(lines) + "\n")
print("\n".join(lines))
PY

ls -lh "$DEST" | tail -n +2 | awk '{print "  ", $5, $9, $10, $11}'
echo "folder: $DEST"
xcrun simctl delete "$UDID" >/dev/null 2>&1 && echo "simulator removed"
exit "$RC"
