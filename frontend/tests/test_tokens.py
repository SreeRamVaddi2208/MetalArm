"""The design system's rules, enforced: colours, type sizes and radii come
from metalarm/theme.py, nowhere else; and the rank tier colours appear only
in the two places allowed to use them.

Checked on every module under ui/, components/ and pages/. There is no
exemption list: a screen that needs a value the tokens lack gets a token.
"""

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1] / "metalarm"

HEX = re.compile(r"#[0-9a-fA-F]{3,8}\b")
RGBA = re.compile(r"rgba?\(")
REM = re.compile(r"\d(\.\d+)?rem\b")
LITERAL_FONT_SIZE = re.compile(r"font_size\s*=\s*\"")
LITERAL_RADIUS = re.compile(r"border_radius\s*=\s*\"")
LITERAL_FONT = re.compile(r"font_family\s*=\s*\"")
TIER = re.compile(r"\b(TIER_COLORS|tier_color)\b")

# The rank badge and the rank-up overlay; nothing else wears a tier colour.
TIER_ALLOWED = {"ui/rank_badge.py", "components/level_up.py"}


def _checked() -> list[Path]:
    files = []
    for folder in ("ui", "components", "pages"):
        files += [p for p in sorted((ROOT / folder).glob("*.py")) if p.name != "__init__.py"]
    return files


def _code_lines(path: Path):
    for number, line in enumerate(path.read_text().splitlines(), start=1):
        if not line.lstrip().startswith("#"):  # a comment may name a colour
            yield number, line


def test_there_is_something_to_check() -> None:
    names = {p.name for p in _checked()}
    assert {"primitives.py", "chrome.py", "design_system.py", "train.py", "home.py"} <= names


def test_no_inline_colours_sizes_or_radii() -> None:
    patterns = (("hex colour", HEX), ("rgba literal", RGBA), ("rem size", REM),
                ("literal font_size", LITERAL_FONT_SIZE), ("literal border_radius", LITERAL_RADIUS),
                ("literal font_family", LITERAL_FONT))
    problems = [f"{path.relative_to(ROOT)}:{n}: {label}: {line.strip()}"
                for path in _checked() for n, line in _code_lines(path)
                for label, pattern in patterns if pattern.search(line)]
    assert not problems, "use theme tokens:\n" + "\n".join(problems)


def test_tier_colours_stay_in_the_badge_and_the_overlay() -> None:
    problems = [f"{path.relative_to(ROOT)}:{n}: {line.strip()}"
                for path in _checked() if str(path.relative_to(ROOT)) not in TIER_ALLOWED
                for n, line in _code_lines(path) if TIER.search(line)]
    assert not problems, "tier colours belong to RankBadge and the rank-up overlay:\n" + "\n".join(problems)


def test_one_accent() -> None:
    """theme.py holds exactly one accent and no other hue tokens."""
    import importlib.util

    spec = importlib.util.spec_from_file_location("theme", ROOT / "theme.py")
    theme = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(theme)
    colours = {k for k, v in vars(theme).items() if k.isupper() and isinstance(v, str) and v.startswith("#")}
    assert colours == {"BG", "SURFACE", "SURFACE_2", "BORDER", "TEXT", "TEXT_2", "TEXT_3", "ACCENT",
                       "ON_ACCENT", "DANGER"}, colours
