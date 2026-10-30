"""Print decisions in one place: page size, bleed and DPI thresholds."""
from dataclasses import dataclass


@dataclass(frozen=True)
class PrintConfig:
    target_dpi: int = 300
    warn_dpi: int = 250
    bleed_mm: float = 0
    page_width_mm: float = 0
    page_height_mm: float = 0


PRINT = PrintConfig()
