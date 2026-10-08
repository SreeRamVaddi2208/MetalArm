"""The native apps' design-system rules, enforced - the twin of
frontend/tests/test_tokens.py, for iOS and Android.

Colours, type sizes and radii come from each app's theme (iOS:
ios/MetalARM/Theme/, Android: android/.../metalarm/theme/), nowhere else; the
rank tier colours appear only in RankBadge (in the theme) and the rank-up
overlay; and both apps' colours match the web app's metalarm/theme.py.

The share cards are exempt: they are rendered to a fixed-size image, not a
screen. A single line can opt out with a `// token-exempt: <why>` comment.

    python scripts/check_client_tokens.py      # exit 1 and a list on failure
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / "ios" / "MetalARM"
THEME_SWIFT = APP / "Theme" / "Theme.swift"
THEME_PY = ROOT / "frontend" / "metalarm" / "theme.py"
ANDROID = ROOT / "android" / "app" / "src" / "main" / "java" / "com" / "sreeram" / "metalarm"
THEME_KT = ANDROID / "theme" / "Theme.kt"

EXEMPT_DIRS = {"Theme"}
EXEMPT_FILES = {"ShareCard.swift", "ContractFixtures.swift"}
TIER_ALLOWED = {"LevelUpView.swift"}

RULES = [
    (re.compile(r"Color\(\s*(hex|red|white):"), "a raw colour - use a Theme colour"),
    (re.compile(r"#[0-9a-fA-F]{6}\b"), "a hex colour - use a Theme colour"),
    (re.compile(r"\.font\(\s*\.system\(\s*size:"), "a fixed font size - use a Theme font"),
    (re.compile(r"\.font\(\s*\.(largeTitle|title|title2|title3|headline|body|callout|subheadline|footnote|caption|caption2)\b"),
     "a system text style - use a Theme font"),
    (re.compile(r"cornerRadius(:|\()\s*\d"), "a numeric radius - use Theme.radius"),
    (re.compile(r"\bTheme\.(dim|faint|card|cardBorder|silver|gold)\b"), "an old token name"),
]
TIER = re.compile(r"\bTheme\.(tier|tierColors)\b")

ANDROID_EXEMPT_DIRS = {"theme"}
ANDROID_EXEMPT_FILES = {"ShareCard.kt"}
# The rank-up overlay lives in Summary.kt.
ANDROID_TIER_ALLOWED = {"Summary.kt"}
ANDROID_RULES = [
    (re.compile(r"\bColor\(\s*0x"), "a raw colour - use a Theme colour"),
    (re.compile(r"#[0-9a-fA-F]{6}\b"), "a hex colour - use a Theme colour"),
    (re.compile(r"\d(\.\d+)?\.sp\b"), "a literal text size - use a Theme style"),
    (re.compile(r"fontSize\s*="), "a font size - use a Theme style"),
    (re.compile(r"(RoundedCornerShape|CornerSize)\(\s*\d"), "a numeric radius - use Theme.radius"),
    (re.compile(r"MaterialTheme\.typography"), "Material type - use a Theme style"),
]

# Theme.swift name -> theme.py name, for the parity check.
PARITY = {
    "bg": "BG", "surface": "SURFACE", "surface2": "SURFACE_2", "border": "BORDER", "text": "TEXT",
    "text2": "TEXT_2", "text3": "TEXT_3", "accent": "ACCENT", "onAccent": "ON_ACCENT", "danger": "DANGER",
}


def checked_files() -> list[Path]:
    return [
        p for p in sorted(APP.rglob("*.swift"))
        if not (set(p.relative_to(APP).parts[:-1]) & EXEMPT_DIRS) and p.name not in EXEMPT_FILES
    ]


def android_files() -> list[Path]:
    return [
        p for p in sorted(ANDROID.rglob("*.kt"))
        if not (set(p.relative_to(ANDROID).parts[:-1]) & ANDROID_EXEMPT_DIRS) and p.name not in ANDROID_EXEMPT_FILES
    ]


def android_violations() -> list[str]:
    found = []
    for path in android_files():
        for number, line in enumerate(path.read_text().splitlines(), start=1):
            if "// token-exempt:" in line:
                continue
            code = line.split("//", 1)[0]
            where = f"{path.relative_to(ROOT)}:{number}"
            for pattern, why in ANDROID_RULES:
                if pattern.search(code):
                    found.append(f"{where}: {why}: {line.strip()}")
            if TIER.search(code) and path.name not in ANDROID_TIER_ALLOWED:
                found.append(f"{where}: a tier colour outside RankBadge and the rank-up overlay: {line.strip()}")
    return found


def android_parity() -> list[str]:
    kotlin = {m[1]: m[2].upper() for m in re.finditer(r"val (\w+) = Color\(0xFF([0-9A-Fa-f]{6})\)", THEME_KT.read_text())}
    web = {m[1]: m[2].upper() for m in re.finditer(r'^(\w+) = "#([0-9A-Fa-f]{6})"', THEME_PY.read_text(), re.M)}
    return [
        f"Android Theme.{name} is #{kotlin.get(name)} but theme.py {web_name} is #{web.get(web_name)}"
        for name, web_name in PARITY.items() if kotlin.get(name) != web.get(web_name)
    ]


def violations() -> list[str]:
    found = []
    for path in checked_files():
        for number, line in enumerate(path.read_text().splitlines(), start=1):
            if "// token-exempt:" in line:
                continue
            code = line.split("//", 1)[0]  # a comment may name a colour
            where = f"{path.relative_to(ROOT)}:{number}"
            for pattern, why in RULES:
                if pattern.search(code):
                    found.append(f"{where}: {why}: {line.strip()}")
            if TIER.search(code) and path.name not in TIER_ALLOWED:
                found.append(f"{where}: a tier colour outside RankBadge and LevelUpView: {line.strip()}")
    return found


def parity() -> list[str]:
    swift = {m[1]: m[2].upper() for m in re.finditer(r"static let (\w+) = Color\(hex: 0x([0-9A-Fa-f]{6})\)",
                                                       THEME_SWIFT.read_text())}
    web = {m[1]: m[2].upper() for m in re.finditer(r'^(\w+) = "#([0-9A-Fa-f]{6})"', THEME_PY.read_text(), re.M)}
    out = []
    for ios_name, web_name in PARITY.items():
        if swift.get(ios_name) != web.get(web_name):
            out.append(f"Theme.{ios_name} is #{swift.get(ios_name)} but theme.py {web_name} is #{web.get(web_name)}")
    return out


def main() -> int:
    problems = violations() + parity() + android_violations() + android_parity()
    for problem in problems:
        print(problem)
    print(f"{len(checked_files())} iOS and {len(android_files())} Android files checked, {len(problems)} problem(s)")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
