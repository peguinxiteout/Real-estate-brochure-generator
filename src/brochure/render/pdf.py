"""PDF output with WeasyPrint. For now only a blank proof of the print geometry (see render_blank_pdf)."""
from pathlib import Path

from brochure.print_config import PRINT, PrintConfig
from brochure.render.geometry import check_page_count


def render_blank_pdf(page_count: int, path: Path, config: PrintConfig = PRINT) -> Path:
    check_page_count(page_count, config)
    return Path(path)
