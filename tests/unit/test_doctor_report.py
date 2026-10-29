"""Report formatting and the check runner."""
from brochure import doctor
from brochure.doctor import Check, format_report, run_checks

OK = Check("Python", True, "3.12.10")
BAD = Check(
    "Ghostscript",
    False,
    "not found",
    ("download the installer", 'setx GS_BIN "C:\\gs\\gswin64c.exe"'),
)


def lines_of(checks):
    return format_report(checks).splitlines()


def test_passing_check_is_one_line_with_name_and_detail_and_no_fix():
    report = format_report([OK])

    line = next(line for line in report.splitlines() if "Python" in line)
    assert line.startswith("[OK]")
    assert "3.12.10" in line
    assert "fix:" not in report


def test_failing_check_is_flagged_and_lists_every_fix_on_its_own_line():
    lines = lines_of([BAD])

    status = next(line for line in lines if "Ghostscript" in line)
    assert status.startswith("[FAIL]")
    assert "not found" in status
    fixes = [line.strip() for line in lines if "fix:" in line]
    assert fixes == ["fix: download the installer", 'fix: setx GS_BIN "C:\\gs\\gswin64c.exe"']


def test_names_are_padded_so_details_line_up():
    lines = lines_of([OK, BAD])

    python_line = next(line for line in lines if line.startswith("[OK]"))
    gs_line = next(line for line in lines if line.startswith("[FAIL]"))
    assert python_line.index("Python") == gs_line.index("Ghostscript")
    assert python_line.index("3.12.10") == gs_line.index("not found")


def test_summary_counts_failures():
    assert lines_of([OK, BAD, BAD])[-1] == "2 of 3 checks failed."


def test_summary_when_everything_passes():
    assert lines_of([OK, OK])[-1] == "All 2 checks passed."


def test_run_checks_returns_the_four_checks_in_a_stable_order(monkeypatch):
    monkeypatch.setattr(doctor, "check_python", lambda: Check("Python", True, "x"))
    monkeypatch.setattr(doctor, "check_weasyprint", lambda: Check("WeasyPrint", True, "x"))
    monkeypatch.setattr(doctor, "check_ghostscript", lambda: Check("Ghostscript", True, "x"))
    monkeypatch.setattr(doctor, "check_fonts", lambda: Check("Bundled fonts", True, "x"))

    assert [c.name for c in run_checks()] == ["Python", "WeasyPrint", "Ghostscript", "Bundled fonts"]
