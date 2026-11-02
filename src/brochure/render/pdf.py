"""PDF output with WeasyPrint. For now only a blank proof of the print geometry (see render_blank_pdf)."""
from pathlib import Path

from brochure.print_config import PRINT, PrintConfig
from brochure.render.geometry import Box, check_page_count


def render_blank_pdf(page_count: int, path: Path, config: PrintConfig = PRINT) -> Path:
    check_page_count(page_count, config)
    return Path(path)


def set_bleed_boxes(pdf, bleed: Box) -> None:
    """WeasyPrint finisher: give every page this BleedBox (see the module docstring for why)."""
    for obj in pdf.objects:
        if isinstance(obj, dict) and obj.get("Type") == "/Page":
            obj["BleedBox"][:] = [bleed.left, bleed.bottom, bleed.right, bleed.top]
