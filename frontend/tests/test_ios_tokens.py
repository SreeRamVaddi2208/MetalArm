"""The iOS app keeps to the same design system: scripts/check_ios_tokens.py,
run as part of the frontend suite (which CI already runs)."""

import importlib.util
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "check_ios_tokens.py"
spec = importlib.util.spec_from_file_location("check_ios_tokens", SCRIPT)
check = importlib.util.module_from_spec(spec)
spec.loader.exec_module(check)


def test_there_is_something_to_check() -> None:
    names = {p.name for p in check.checked_files()}
    assert {"HomeView.swift", "WorkoutView.swift", "LibraryHomeView.swift"} <= names


def test_views_use_only_tokens() -> None:
    assert check.violations() == []


def test_ios_colours_match_the_web() -> None:
    assert check.parity() == []
