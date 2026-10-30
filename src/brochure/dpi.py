"""Pixel and DPI maths for print slots."""
import math
from fractions import Fraction

MM_PER_INCH = Fraction("25.4")


def _exact(value: float) -> Fraction:
    """The decimal the caller wrote (216, 38.1), not its binary float approximation."""
    return Fraction(str(value))


def min_pixels(size_mm: float, dpi: int) -> int:
    return math.ceil(_exact(size_mm) / MM_PER_INCH * dpi)
