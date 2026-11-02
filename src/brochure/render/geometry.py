"""Print geometry for one page: the PDF page boxes and the crop mark segments, in millimetres and in points.

Pure maths from PrintConfig; no WeasyPrint import. Coordinates have their origin at the lower-left corner of the trim
box, y upwards, which is how WeasyPrint writes its pages: the TrimBox is [0, 0, w, h] and the BleedBox and MediaBox
start at negative coordinates.
"""
import math
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

    def contains(self, other: "Box") -> bool:
        """True when other lies inside this box (touching edges count as inside)."""
        return (self.left <= other.left and self.bottom <= other.bottom
                and other.right <= self.right and other.top <= self.top)

    def grown(self, by: float) -> "Box":
        return Box(self.left - by, self.bottom - by, self.right + by, self.top + by)

    def to_pt(self) -> "Box":
        return Box(*(mm_to_pt(v) for v in astuple(self)))


@dataclass(frozen=True)
class Segment:
    """A straight line from (x0, y0), the end nearer the trim, to (x1, y1)."""

    x0: float
    y0: float
    x1: float
    y1: float

    @property
    def length(self) -> float:
        return math.hypot(self.x1 - self.x0, self.y1 - self.y0)

    @property
    def bounds(self) -> Box:
        return Box(min(self.x0, self.x1), min(self.y0, self.y1), max(self.x0, self.x1), max(self.y0, self.y1))

    def to_pt(self) -> "Segment":
        return Segment(*(mm_to_pt(v) for v in astuple(self)))


@dataclass(frozen=True)
class PageGeometry:
    media: Box
    bleed: Box
    trim: Box
    crop_marks: tuple[Segment, ...] = ()


def _crop_marks(trim: Box, near: float, far: float) -> tuple[Segment, ...]:
    """Two marks per trim corner, on the extensions of the trim lines, from near to far outside the trim edge."""
    marks = []
    for x, sx in ((trim.left, -1), (trim.right, 1)):
        for y, sy in ((trim.bottom, -1), (trim.top, 1)):
            marks.append(Segment(x + sx * near, y, x + sx * far, y))  # horizontal, on the line y = trim edge
            marks.append(Segment(x, y + sy * near, x, y + sy * far))  # vertical, on the line x = trim edge
    return tuple(marks)


def page_geometry_mm(config: PrintConfig = PRINT) -> PageGeometry:
    trim = Box(0, 0, config.page_width_mm, config.page_height_mm)
    near = config.crop_mark_offset_mm
    far = near + config.crop_mark_length_mm
    outside_trim = config.bleed_mm + config.slug_beyond_bleed_mm
    if near <= config.bleed_mm:
        raise ValueError(
            f"crop marks must start outside the bleed: crop_mark_offset_mm ({near}) must be more than bleed_mm "
            f"({config.bleed_mm})"
        )
    if far > outside_trim:
        raise ValueError(
            f"crop marks must end inside the media box: crop_mark_offset_mm + crop_mark_length_mm ({far}) must be at "
            f"most bleed_mm + slug_beyond_bleed_mm ({outside_trim})"
        )
    return PageGeometry(
        media=trim.grown(outside_trim),
        bleed=trim.grown(config.bleed_mm),
        trim=trim,
        crop_marks=_crop_marks(trim, near, far),
    )


def page_geometry_pt(config: PrintConfig = PRINT) -> PageGeometry:
    mm = page_geometry_mm(config)
    return PageGeometry(media=mm.media.to_pt(), bleed=mm.bleed.to_pt(), trim=mm.trim.to_pt())
