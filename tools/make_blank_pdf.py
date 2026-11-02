"""Write the blank print-geometry proof PDF, to open and check by eye.

Usage: python tools/make_blank_pdf.py [--out PATH] [--pages N]   (default: sample/blank-8pp.pdf, 8 pages)
Needs WeasyPrint with Pango (run it in WSL).
"""
import argparse
from pathlib import Path

from brochure.render.pdf import render_blank_pdf

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUT = ROOT / "sample" / "blank-8pp.pdf"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT, help=f"PDF to write (default: {DEFAULT_OUT})")
    parser.add_argument("--pages", type=int, default=8, help="page count, a positive multiple of 4 (default: 8)")
    args = parser.parse_args(argv)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    path = render_blank_pdf(args.pages, args.out)
    print(f"wrote {path} ({path.stat().st_size} bytes, {args.pages} pages)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
