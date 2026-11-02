"""Write the blank print-geometry proof PDF, to open and check by eye.

Usage: python tools/make_blank_pdf.py [--out PATH] [--pages N]   (default: sample/blank-8pp.pdf, 8 pages)
Needs WeasyPrint with Pango (run it in WSL).
"""
import argparse
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUT = ROOT / "sample" / "blank-8pp.pdf"


def main(argv: list[str] | None = None) -> int:
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
