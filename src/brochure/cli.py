"""Command line entry point: `brochure <command>`."""
from __future__ import annotations

import argparse

from brochure.doctor import format_report, run_checks


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="brochure", description="Print-ready real estate brochure generator")
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("doctor", help="check Python, WeasyPrint, Ghostscript and bundled fonts")
    parser.parse_args(argv)

    checks = run_checks()
    print(format_report(checks))
    return 0 if all(c.ok for c in checks) else 1
