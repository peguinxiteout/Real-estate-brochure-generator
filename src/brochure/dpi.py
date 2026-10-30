"""Pixel and DPI maths for print slots."""
import math
from enum import StrEnum
from fractions import Fraction

MM_PER_INCH = Fraction("25.4")


def _exact(value: float) -> Fraction:
    """The decimal the caller wrote (216, 38.1), not its binary float approximation."""
    return Fraction(str(value))


def min_pixels(size_mm: float, dpi: int) -> int:
    return math.ceil(_exact(size_mm) / MM_PER_INCH * dpi)


def effective_dpi(width_px: int, height_px: int, slot_width_mm: float, slot_height_mm: float) -> float:
    across = Fraction(width_px) / (_exact(slot_width_mm) / MM_PER_INCH)
    down = Fraction(height_px) / (_exact(slot_height_mm) / MM_PER_INCH)
    return float(min(across, down))


class DpiStatus(StrEnum):
    PASS = "pass"
    WARN = "warn"
    FAIL = "fail"


def classify_dpi(dpi: float) -> DpiStatus:
    if dpi >= 300:
        return DpiStatus.PASS
    if dpi >= 250:
        return DpiStatus.WARN
    return DpiStatus.FAIL
