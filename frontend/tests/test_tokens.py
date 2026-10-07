"""The design system's one rule: colours, type sizes and radii come from
metalarm/theme.py, nowhere else.

Checked on the component library (metalarm/ui/) and on every page built for
the overhaul. Pages from before it are listed in LEGACY and are exempt until
they are rebuilt - the list should only ever get shorter.
"""

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1] / "metalarm"

# Rebuilt in a later phase of the overhaul; remove each as it is.
LEGACY = {
    "components/duel_card.py", "components/exercise_demo.py",
    "components/layout.py", "components/level_up.py", "components/party_card.py",
    "components/presets.py", "components/quest_card.py",
    "components/rest_timer.py", "components/reward_card.py", "components/scroll_reveal.py",
    "components/stat_panel.py",
    "components/voice_log.py", "components/workout.py",
    "pages/dashboard.py", "pages/duels.py", "pages/login.py", "pages/parties.py",
    "pages/profile.py", "pages/progress.py", "pages/rewards.py",
    "pages/workout.py",
}

HEX = re.compile(r"#[0-9a-fA-F]{3,8}\b")
RGBA = re.compile(r"rgba?\(")
LITERAL_FONT_SIZE = re.compile(r"font_size\s*=\s*\"")
LITERAL_RADIUS = re.compile(r"border_radius\s*=\s*\"")


def _checked() -> list[Path]:
    files = sorted((ROOT / "ui").glob("*.py"))
    for folder in ("components", "pages"):
        for path in sorted((ROOT / folder).glob("*.py")):
            rel = f"{folder}/{path.name}"
            if path.name != "__init__.py" and rel not in LEGACY:
                files.append(path)
    return files


def test_there_is_something_to_check() -> None:
    names = {p.name for p in _checked()}
    assert {"primitives.py", "chrome.py", "gallery.py", "explore.py"} <= names


def test_no_inline_colours_sizes_or_radii() -> None:
    patterns = (("hex colour", HEX), ("rgba literal", RGBA),
                ("literal font_size", LITERAL_FONT_SIZE),
                ("literal border_radius", LITERAL_RADIUS))
    problems = []
    for path in _checked():
        for number, line in enumerate(path.read_text().splitlines(), start=1):
            if line.lstrip().startswith("#"):
                continue  # a comment may name a colour
            for label, pattern in patterns:
                if pattern.search(line):
                    problems.append(f"{path.relative_to(ROOT)}:{number}: {label}: {line.strip()}")
    assert not problems, "use theme tokens:\n" + "\n".join(problems)


def test_legacy_entries_still_exist() -> None:
    """A stale LEGACY entry would quietly exempt a future file of that name."""
    missing = [rel for rel in LEGACY if not (ROOT / rel).exists()]
    assert not missing, missing
