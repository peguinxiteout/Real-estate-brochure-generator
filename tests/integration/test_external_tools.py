"""Tests that touch the real tools. They skip, with a reason, when a tool is missing."""
import re
import subprocess

import pytest

pytestmark = pytest.mark.integration


def test_weasyprint_really_imports(weasyprint_module):
    assert hasattr(weasyprint_module, "HTML")
    assert re.match(r"\d+", weasyprint_module.__version__)


def test_ghostscript_found_by_doctor_runs_and_reports_a_version(ghostscript_exe):
    result = subprocess.run([str(ghostscript_exe), "--version"], capture_output=True, text=True, timeout=30)

    assert result.returncode == 0
    assert re.match(r"\d+\.\d+", result.stdout.strip())
