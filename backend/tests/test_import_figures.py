"""The pack importer refuses anything it could not credit."""

from pathlib import Path

import pytest

from scripts.import_figures import ManifestError, read_manifest


def _manifest(tmp_path: Path, body: str) -> Path:
    path = tmp_path / "manifest.csv"
    path.write_text("slug,file,license,author,source_url\n" + body)
    return path


def test_reads_a_complete_row(tmp_path: Path) -> None:
    rows = read_manifest(_manifest(tmp_path, "squat,a.png,Pack licence,Studio,\n"), {"squat"})
    assert rows[0]["author"] == "Studio"


@pytest.mark.parametrize("row", ["squat,a.png,,Studio,\n", "squat,a.png,Pack licence,,\n", "squat,,Pack licence,Studio,\n",
                                 "nope,a.png,Pack licence,Studio,\n",
                                 "squat,a.png,L,S,\nsquat,b.png,L,S,\n"])
def test_refuses_what_it_cannot_credit_or_place(tmp_path: Path, row: str) -> None:
    with pytest.raises(ManifestError):
        read_manifest(_manifest(tmp_path, row), {"squat"})
