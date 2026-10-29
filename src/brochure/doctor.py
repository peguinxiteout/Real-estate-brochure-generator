"""Environment checks behind `brochure doctor`."""
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

DEFAULT_GS_ROOT = Path(r"C:\Program Files\gs")


@dataclass(frozen=True)
class GsLookup:
    path: Path | None = None
    source: str | None = None


def find_ghostscript(*, which=None, gs_root: Path | None = None) -> GsLookup:
    configured = os.environ.get("GS_BIN")
    if configured and Path(configured).is_file():
        return GsLookup(Path(configured), "GS_BIN")
    return GsLookup()
