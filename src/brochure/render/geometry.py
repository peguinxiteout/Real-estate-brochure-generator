"""Print geometry for one page: the PDF page boxes and the crop mark segments, in millimetres and in points.

Pure maths from PrintConfig; no WeasyPrint import. Coordinates have their origin at the lower-left corner of the trim
box, y upwards, which is how WeasyPrint writes its pages: the TrimBox is [0, 0, w, h] and the BleedBox and MediaBox
start at negative coordinates.
"""
from dataclasses import astuple, dataclass

from brochure.print_config import PRINT, PrintConfig

PT_PER_MM = 72 / 25.4


def mm_to_pt(mm: float) -> float:
    return mm * PT_PER_MM


@dataclass(frozen=True)
class Box:
    """A rectangle as in a PDF box: [left, bottom, right, top]."""

    left: float
    bottom: float
    right: float
    top: float

    @property
    def width(self) -> float:
        return self.right - self.left

    @property
    def height(self) -> float:
        return self.top - self.bottom

    def grown(self, by: float) -> "Box":
        return Box(self.left - by, self.bottom - by, self.right + by, self.top + by)

    def to_pt(self) -> "Box":
        return Box(*(mm_to_pt(v) for v in astuple(self)))


@dataclass(frozen=True)
class PageGeometry:
    media: Box
    bleed: Box
    trim: Box


def page_geometry_mm(config: PrintConfig = PRINT) -> PageGeometry:
    trim = Box(0, 0, config.page_width_mm, config.page_height_mm)
    zero = Box(0, 0, 0, 0)
    return PageGeometry(media=zero, bleed=trim.grown(config.bleed_mm), trim=trim)
