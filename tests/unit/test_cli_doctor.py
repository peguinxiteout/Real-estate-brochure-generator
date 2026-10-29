"""`brochure doctor`: prints the report, exit code 0 when healthy and 1 when something is missing."""
import pytest

from brochure import cli
from brochure.doctor import Check

GOOD = Check("Python", True, "3.12.10")
BAD = Check("Ghostscript", False, "not found", ("download the installer",))


def test_doctor_prints_the_report_and_exits_zero_when_everything_passes(monkeypatch, capsys):
    monkeypatch.setattr(cli, "run_checks", lambda: [GOOD])

    code = cli.main(["doctor"])

    out = capsys.readouterr().out
    assert code == 0
    assert "Python" in out
    assert "All 1 checks passed." in out


def test_doctor_exits_one_and_prints_the_fix_when_something_is_missing(monkeypatch, capsys):
    monkeypatch.setattr(cli, "run_checks", lambda: [GOOD, BAD])

    code = cli.main(["doctor"])

    out = capsys.readouterr().out
    assert code == 1
    assert "[FAIL]" in out
    assert "fix: download the installer" in out


def test_unknown_command_is_rejected_by_argparse():
    with pytest.raises(SystemExit) as excinfo:
        cli.main(["frobnicate"])

    assert excinfo.value.code == 2
