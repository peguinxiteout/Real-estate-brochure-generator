"""Pixel and DPI maths for print slots."""
import math

MM_PER_INCH = 25.4


def min_pixels(size_mm: float, dpi: int) -> int:
    return math.ceil(size_mm / MM_PER_INCH * dpi)
