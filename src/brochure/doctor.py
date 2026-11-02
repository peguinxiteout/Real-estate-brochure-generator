"""Environment checks behind `brochure doctor`."""
from __future__ import annotations

import importlib
import os
import re
import shutil
import sys
from dataclasses import dataclass
from pathlib import Path

from brochure.fonts import BUNDLED_FAMILIES, missing_font_files

MIN_PYTHON = (3, 12)
DEFAULT_GS_ROOT = Path(r"C:\Program Files\gs")
GS_PATH_NAMES_WINDOWS = ("gswin64c", "gswin32c", "gs")
GS_PATH_NAMES_POSIX = ("gs",)
# <repo>/src/brochure/doctor.py -> <repo>/assets/fonts (valid for the editable install used in development)
DEFAULT_FONTS_DIR = Path(__file__).resolve().parents[2] / "assets" / "fonts"

PIP_FIX = "python -m pip install weasyprint"
MSYS2_FIXES = (
    "winget install MSYS2.MSYS2",
    'C:\\msys64\\usr\\bin\\bash.exe -lc "pacman -S --noconfirm mingw-w64-x86_64-pango"',
    "setx WEASYPRINT_DLL_DIRECTORIES C:\\msys64\\mingw64\\bin    (then open a new terminal)",
)
APT_PANGO_FIXES = ("sudo apt install libpango-1.0-0 libpangoft2-1.0-0 libharfbuzz-subset0",)
APT_GS_FIX = "sudo apt install ghostscript"
SETX_GS_BIN_FIX = 'setx GS_BIN "<full path to gswin64c.exe>"'
EXPORT_GS_BIN_FIX = 'export GS_BIN="<full path to gs>"    (add it to ~/.bashrc)'
GS_DOWNLOAD_FIX = "download the 64-bit installer from https://ghostscript.com/releases/gsdnld.html"


def _is_windows() -> bool:
    return sys.platform == "win32"


@dataclass(frozen=True)
class Check:
    name: str
    ok: bool
    detail: str
    fixes: tuple[str, ...] = ()


@dataclass(frozen=True)
class GsLookup:
    path: Path | None = None
    source: str | None = None
    note: str | None = None


def _version_key(exe: Path) -> tuple[int, ...]:
    # <root>/gs10.04.0/bin/gswin64c.exe -> (10, 4, 0); numeric, so 10.x sorts after 9.x
    return tuple(int(n) for n in re.findall(r"\d+", exe.parent.parent.name))


def find_ghostscript(*, which=None, gs_root: Path | None = None) -> GsLookup:
    """Lookup order: GS_BIN env var, then PATH, then (Windows only) the highest version under C:\\Program Files\\gs."""
    which = which or shutil.which
    gs_root = DEFAULT_GS_ROOT if gs_root is None else gs_root

    note = None
    configured = os.environ.get("GS_BIN")
    if configured:
        if Path(configured).is_file():
            return GsLookup(Path(configured), "GS_BIN")
        note = f"GS_BIN is set to {configured} but that file does not exist"

    for name in GS_PATH_NAMES_WINDOWS if _is_windows() else GS_PATH_NAMES_POSIX:
        found = which(name)
        if found:
            return GsLookup(Path(found), "PATH", note)

    if not _is_windows():
        return GsLookup(note=note)

    installed = sorted(gs_root.glob("*/bin/gswin64c.exe"), key=_version_key, reverse=True)
    if installed:
        return GsLookup(installed[0], "Program Files", note)

    return GsLookup(note=note)


def check_python(version: tuple[int, int, int] | None = None) -> Check:
    version = version or sys.version_info[:3]
    shown = ".".join(str(n) for n in version)
    if version[:2] >= MIN_PYTHON:
        return Check("Python", True, shown)
    needed = ".".join(str(n) for n in MIN_PYTHON)
    return Check("Python", False, f"{shown} (need {needed} or newer)", ("winget install Python.Python.3.12",))


def _last_line(exc: BaseException) -> str:
    lines = [line.strip() for line in str(exc).splitlines() if line.strip()]
    return lines[-1] if lines else type(exc).__name__


def check_weasyprint(importer=importlib.import_module) -> Check:
    try:
        module = importer("weasyprint")
    except ModuleNotFoundError as exc:
        return Check("WeasyPrint", False, f"not installed ({_last_line(exc)})", (PIP_FIX,))
    except Exception as exc:  # OSError / ImportError when the Pango libraries cannot be loaded
        return Check("WeasyPrint", False, _last_line(exc), MSYS2_FIXES if _is_windows() else APT_PANGO_FIXES)
    return Check("WeasyPrint", True, f"version {getattr(module, '__version__', 'unknown')}")


def check_ghostscript(lookup: GsLookup | None = None) -> Check:
    lookup = find_ghostscript() if lookup is None else lookup
    if lookup.path is not None:
        return Check("Ghostscript", True, f"{lookup.path} (via {lookup.source})")
    windows = _is_windows()
    searched = "GS_BIN, PATH, C:\\Program Files\\gs" if windows else "GS_BIN, PATH"
    detail = f"not found (looked at {searched})"
    fixes = [GS_DOWNLOAD_FIX if windows else APT_GS_FIX]
    if lookup.note:
        detail = f"{lookup.note}; {detail}"
        fixes.append(SETX_GS_BIN_FIX if windows else EXPORT_GS_BIN_FIX)
    return Check("Ghostscript", False, detail, tuple(fixes))


def check_fonts(fonts_dir: Path | None = None) -> Check:
    fonts_dir = DEFAULT_FONTS_DIR if fonts_dir is None else fonts_dir
    families = ", ".join(BUNDLED_FAMILIES)
    if not fonts_dir.is_dir():
        detail = f"{fonts_dir} not found"
    else:
        missing = missing_font_files(fonts_dir)
        if not missing:
            return Check("Bundled fonts", True, f"{families} in {fonts_dir}")
        detail = f"missing from {fonts_dir}: {', '.join(missing)}"
    return Check(
        "Bundled fonts",
        False,
        detail,
        (
            "git restore assets/fonts",
            "or download Inter and Open Sans from Google Fonts and copy the static TTFs (Inter 18pt Regular, SemiBold, "
            "Bold; Open Sans Regular, Italic, SemiBold, Bold) with each family's OFL.txt into assets/fonts/Inter and "
            "assets/fonts/OpenSans",
        ),
    )


def run_checks() -> list[Check]:
    return [check_python(), check_weasyprint(), check_ghostscript(), check_fonts()]


def format_report(checks: list[Check]) -> str:
    name_width = max(len(c.name) for c in checks)
    lines = ["brochure doctor", ""]
    for c in checks:
        tag = "[OK]" if c.ok else "[FAIL]"
        lines.append(f"{tag:<7}{c.name:<{name_width}}  {c.detail}")
        lines.extend(f"{'':<7}{'':<{name_width}}  fix: {fix}" for fix in c.fixes)
    failed = sum(not c.ok for c in checks)
    lines.append("")
    lines.append(f"{failed} of {len(checks)} checks failed." if failed else f"All {len(checks)} checks passed.")
    return "\n".join(lines)
