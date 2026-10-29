"""Environment checks behind `brochure doctor`."""
from __future__ import annotations

import os
import re
import shutil
from dataclasses import dataclass
from pathlib import Path

DEFAULT_GS_ROOT = Path(r"C:\Program Files\gs")
GS_PATH_NAMES = ("gswin64c", "gswin32c", "gs")


@dataclass(frozen=True)
class GsLookup:
    path: Path | None = None
    source: str | None = None
    note: str | None = None


def _version_key(exe: Path) -> tuple[int, ...]:
    # <root>/gs10.04.0/bin/gswin64c.exe -> (10, 4, 0); numeric, so 10.x sorts after 9.x
    return tuple(int(n) for n in re.findall(r"\d+", exe.parent.parent.name))


def find_ghostscript(*, which=None, gs_root: Path | None = None) -> GsLookup:
    """Lookup order: GS_BIN env var, then PATH, then the highest version under C:\\Program Files\\gs."""
    which = which or shutil.which
    gs_root = DEFAULT_GS_ROOT if gs_root is None else gs_root

    note = None
    configured = os.environ.get("GS_BIN")
    if configured:
        if Path(configured).is_file():
            return GsLookup(Path(configured), "GS_BIN")
        note = f"GS_BIN is set to {configured} but that file does not exist"

    for name in GS_PATH_NAMES:
        found = which(name)
        if found:
            return GsLookup(Path(found), "PATH", note)

    installed = sorted(gs_root.glob("*/bin/gswin64c.exe"), key=_version_key, reverse=True)
    if installed:
        return GsLookup(installed[0], "Program Files", note)

    return GsLookup(note=note)
