"""Shared fixtures. Fixtures for external tools skip with an explicit reason; they never pass silently."""
import importlib

import pytest

from brochure.doctor import find_ghostscript


@pytest.fixture
def weasyprint_module():
    try:
        return importlib.import_module("weasyprint")
    except Exception as exc:  # ModuleNotFoundError, or OSError when the Pango libraries are missing
        lines = [line.strip() for line in str(exc).splitlines() if line.strip()]
        reason = lines[-1] if lines else type(exc).__name__
        pytest.skip(f"WeasyPrint is not importable ({type(exc).__name__}: {reason}). Run `brochure doctor` for the fix.")


@pytest.fixture
def ghostscript_exe():
    lookup = find_ghostscript()
    if lookup.path is None:
        pytest.skip("Ghostscript not found (looked at GS_BIN, PATH, C:\\Program Files\\gs). Run `brochure doctor` for the fix.")
    return lookup.path
