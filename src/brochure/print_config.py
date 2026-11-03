"""Print decisions in one place: page size, bleed, slug, crop marks and DPI thresholds."""
from dataclasses import dataclass


@dataclass(frozen=True)
class PrintConfig:
    target_dpi: int = 300
    warn_dpi: int = 250
    bleed_mm: float = 3
    page_width_mm: float = 210
    page_height_mm: float = 297
    # Slug: the strip outside the bleed that holds the crop marks. Measured from the bleed edge, not the trim, so the
    # MediaBox is trim + 2 x (bleed_mm + slug_beyond_bleed_mm) = 236 x 323 mm. Provisional until the printer's spec arrives.
    slug_beyond_bleed_mm: float = 10
    # Crop marks (provisional): the near end of each mark is crop_mark_offset_mm from the trim edge (so 2 mm clear of
    # the bleed), and it runs crop_mark_length_mm outwards (ending 3 mm inside the MediaBox). Line weight in points.
    crop_mark_offset_mm: float = 5
    crop_mark_length_mm: float = 5
    crop_mark_weight_pt: float = 0.25
    # Safe area (provisional): text and QR slots keep at least this far inside the trim, clear of the cutting tolerance.
    safe_margin_mm: float = 10
    # Text measured taller than its slot by more than this is reported as overflow (smaller is layout rounding).
    text_overflow_tolerance_mm: float = 0.5
    # Layout: the most white space between two consecutive blocks on a page (see positions.gap_problems).
    max_block_gap_mm: float = 15
    # A printed booklet is folded from sheets of 4 pages, so the page count is a positive multiple of this.
    page_count_multiple: int = 4


PRINT = PrintConfig()
