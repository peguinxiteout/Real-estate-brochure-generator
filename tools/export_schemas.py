"""Write the JSON Schema for every contract model to contracts/json/.

Usage: python tools/export_schemas.py [--out DIR]
"""
import argparse
from pathlib import Path

from brochure.contracts.export import write_schemas

DEFAULT_OUT = Path(__file__).resolve().parents[1] / "contracts" / "json"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT, help=f"output folder (default: {DEFAULT_OUT})")
    args = parser.parse_args()
    for path in write_schemas(args.out):
        print(f"wrote {path}")


if __name__ == "__main__":
    main()
