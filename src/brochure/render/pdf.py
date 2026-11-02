"""PDF output with WeasyPrint. For now only a blank proof of the print geometry (see render_blank_pdf)."""
from pathlib import Path

from brochure.print_config import PRINT, PrintConfig
from brochure.render.geometry import Box, check_page_count


def render_blank_pdf(page_count: int, path: Path, config: PrintConfig = PRINT) -> Path:
    check_page_count(page_count, config)
    from weasyprint import HTML  # imported here so this module, and the page count check, work without Pango

    path = Path(path)
    HTML(string=_blank_html(page_count, config)).write_pdf(path)
    return path


def _blank_html(page_count: int, config: PrintConfig) -> str:
    sheets = "
".join(f'<section class="sheet"><p class="number">{n}</p></section>' for n in range(1, page_count + 1))
    return f"""<!doctype html>
<html><head><meta charset="utf-8"><style>
@page {{ size: {config.page_width_mm}mm {config.page_height_mm}mm; margin: 0; }}
html, body {{ margin: 0; }}
.sheet {{ position: relative; width: {config.page_width_mm}mm; height: {config.page_height_mm}mm; break-after: page; }}
.sheet:last-child {{ break-after: auto; }}
</style></head><body>
{sheets}
</body></html>"""


def set_bleed_boxes(pdf, bleed: Box) -> None:
    """WeasyPrint finisher: give every page this BleedBox (see the module docstring for why)."""
    for obj in pdf.objects:
        if isinstance(obj, dict) and obj.get("Type") == "/Page":
            obj["BleedBox"][:] = [bleed.left, bleed.bottom, bleed.right, bleed.top]
