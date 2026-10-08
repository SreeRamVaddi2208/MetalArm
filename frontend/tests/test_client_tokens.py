"""The iOS and Android apps keep to the same design system as the web:
scripts/check_client_tokens.py, run as part of the frontend suite (which CI
already runs)."""

import importlib.util
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "check_client_tokens.py"
spec = importlib.util.spec_from_file_location("check_client_tokens", SCRIPT)
check = importlib.util.module_from_spec(spec)
spec.loader.exec_module(check)


def test_there_is_something_to_check() -> None:
    names = {p.name for p in check.checked_files()}
    assert {"HomeView.swift", "WorkoutView.swift", "LibraryHomeView.swift"} <= names
    android = {p.name for p in check.android_files()}
    assert {"Home.kt", "Workout.kt", "LibraryScreens.kt"} <= android


def test_ios_views_use_only_tokens() -> None:
    assert check.violations() == []


def test_ios_colours_match_the_web() -> None:
    assert check.parity() == []


def test_android_screens_use_only_tokens() -> None:
    assert check.android_violations() == []


def test_android_colours_match_the_web() -> None:
    assert check.android_parity() == []
