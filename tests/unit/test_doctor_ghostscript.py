"""Ghostscript lookup order: GS_BIN env var, then PATH, then C:\\Program Files\\gs."""
from pathlib import Path

import pytest

from brochure.doctor import find_ghostscript


def make_exe(path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("")
    return path


def no_path_hit(name: str) -> None:
    return None


@pytest.fixture(autouse=True)
def clean_env(monkeypatch):
    monkeypatch.delenv("GS_BIN", raising=False)


def test_nothing_found_returns_no_path(tmp_path):
    result = find_ghostscript(which=no_path_hit, gs_root=tmp_path / "missing")

    assert result.path is None
    assert result.source is None


def test_gs_bin_env_var_wins_over_path_and_program_files(monkeypatch, tmp_path):
    from_env = make_exe(tmp_path / "custom" / "gswin64c.exe")
    from_path = make_exe(tmp_path / "onpath" / "gswin64c.exe")
    root = tmp_path / "gs"
    make_exe(root / "gs10.04.0" / "bin" / "gswin64c.exe")
    monkeypatch.setenv("GS_BIN", str(from_env))

    result = find_ghostscript(which=lambda name: str(from_path), gs_root=root)

    assert result.path == from_env
    assert result.source == "GS_BIN"


def test_path_is_used_when_gs_bin_is_unset_and_beats_program_files(tmp_path):
    from_path = make_exe(tmp_path / "onpath" / "gswin64c.exe")
    root = tmp_path / "gs"
    make_exe(root / "gs10.04.0" / "bin" / "gswin64c.exe")

    result = find_ghostscript(which=lambda name: str(from_path), gs_root=root)

    assert result.path == from_path
    assert result.source == "PATH"


def test_program_files_is_last_resort_and_picks_the_highest_version(tmp_path):
    root = tmp_path / "gs"
    make_exe(root / "gs9.56.1" / "bin" / "gswin64c.exe")
    newest = make_exe(root / "gs10.04.0" / "bin" / "gswin64c.exe")

    result = find_ghostscript(which=no_path_hit, gs_root=root)

    assert result.path == newest
    assert result.source == "Program Files"


def test_gs_bin_pointing_at_a_missing_file_falls_through_and_says_so(monkeypatch, tmp_path):
    from_path = make_exe(tmp_path / "onpath" / "gswin64c.exe")
    bogus = tmp_path / "nope" / "gswin64c.exe"
    monkeypatch.setenv("GS_BIN", str(bogus))

    result = find_ghostscript(which=lambda name: str(from_path), gs_root=tmp_path / "gs")

    assert result.path == from_path
    assert result.source == "PATH"
    assert "GS_BIN" in result.note
    assert str(bogus) in result.note
