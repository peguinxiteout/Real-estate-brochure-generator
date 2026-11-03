"""Every third-party package the code imports directly is declared in pyproject.toml."""
import ast
import re
import sys
import tomllib
from pathlib import Path

ROOT = Path(__file__).parents[2]
SRC = ROOT / "src" / "brochure"

# import name -> distribution name, where they differ or the import is a namespace
DISTRIBUTIONS = {"PIL": "Pillow", "langgraph": "langgraph"}


def declared() -> dict[str, str]:
    """Distribution name (lower case) -> its requirement string."""
    requirements = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))["project"]["dependencies"]
    return {re.split(r"[\[<>=!~ ]", r, maxsplit=1)[0].lower(): r for r in requirements}


def imported_third_party() -> set[str]:
    found = set()
    for path in SRC.rglob("*.py"):
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            names = [a.name for a in node.names] if isinstance(node, ast.Import) else [node.module] if isinstance(node, ast.ImportFrom) and node.level == 0 else []
            found |= {n.split(".")[0] for n in names}
    return {n for n in found if n not in sys.stdlib_module_names and n != "brochure"}


def test_every_directly_imported_package_is_declared():
    dists = declared()
    missing = sorted(n for n in imported_third_party() if DISTRIBUTIONS.get(n, n).lower() not in dists)
    assert missing == [], f"imported but not in pyproject.toml dependencies: {missing}"


def test_httpx_is_pinned_like_the_other_pinned_dependencies():
    assert re.fullmatch(r"httpx==\d+\.\d+\.\d+", declared()["httpx"])


def test_weasyprint_is_pinned_to_the_version_the_bleed_box_finisher_was_checked_on():
    assert declared()["weasyprint"] == "weasyprint==70.0"
