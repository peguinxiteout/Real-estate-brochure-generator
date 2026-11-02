"""PDF output with WeasyPrint. For now only a blank proof of the print geometry (see render_blank_pdf).

What WeasyPrint (checked on 70.0) writes for `@page { size: W H; bleed: B; marks: crop }`:
- MediaBox = the page box grown by the CSS `bleed` on every edge; TrimBox = the page box, origin at its lower-left.
- BleedBox = the TrimBox grown by min(B, 10 pt). Its "bleed" is the whole area outside the trim, so with B = bleed +
  slug (13 mm) its BleedBox lands 10 pt (3.53 mm) outside the trim, not 3 mm.
- `marks: crop` draws 1 px (0.75 pt) lines from the MediaBox edge in to B / 2 from it, and only on a page with a
  background. Neither the weight nor the position can be set.

So the CSS bleed is set to bleed + slug (giving the right MediaBox), WeasyPrint's marks are off, the crop marks are
drawn here as vector lines from the geometry, and a finisher rewrites each page's BleedBox to the 3 mm bleed.
"""
from pathlib import Path

from brochure.print_config import PRINT, PrintConfig
from brochure.render.geometry import Box, PageGeometry, check_page_count, page_geometry_pt

PROOF_FILL_RGB = (214, 230, 245)  # light blue, fills the bleed box of the blank proof
PROOF_TRIM_LINE_RGB = (90, 110, 130)
PROOF_TRIM_LINE_PT = 0.5
CROP_MARK_RGB = (0, 0, 0)


def render_blank_pdf(page_count: int, path: Path, config: PrintConfig = PRINT) -> Path:
    """Write a blank proof of the print geometry: page_count pages, each with the page boxes and crop marks, a
    light-coloured fill over the bleed box, a thin rectangle on the trim line and its page number in the middle.

    The page number is set in a system sans-serif font: the brand fonts are not committed yet.
    """
    check_page_count(page_count, config)
    from weasyprint import HTML  # imported here so this module, and the page count check, work without Pango

    geometry = page_geometry_pt(config)
    path = Path(path)
    HTML(string=_blank_html(page_count, geometry)).write_pdf(
        path, finisher=lambda _document, pdf: set_bleed_boxes(pdf, geometry.bleed)
    )
    return path


def _rgb(rgb: tuple[int, int, int]) -> str:
    return "rgb({}, {}, {})".format(*rgb)


def _proof_svg(g: PageGeometry) -> str:
    """The MediaBox as an SVG in points, y downwards from its top-left corner."""

    def x(v: float) -> float:
        return v - g.media.left

    def y(v: float) -> float:
        return g.media.top - v

    def rect(box: Box, attrs: str) -> str:
        return f'<rect x="{x(box.left)}" y="{y(box.top)}" width="{box.width}" height="{box.height}" {attrs}/>'

    marks = "".join(
        f'<line x1="{x(m.x0)}" y1="{y(m.y0)}" x2="{x(m.x1)}" y2="{y(m.y1)}"/>' for m in g.crop_marks
    )
    return (
        f'<svg class="proof" xmlns="http://www.w3.org/2000/svg" width="{g.media.width}pt" height="{g.media.height}pt"'
        f' viewBox="0 0 {g.media.width} {g.media.height}">'
        + rect(g.bleed, f'fill="{_rgb(PROOF_FILL_RGB)}" stroke="none"')
        + rect(g.trim, f'fill="none" stroke="{_rgb(PROOF_TRIM_LINE_RGB)}" stroke-width="{PROOF_TRIM_LINE_PT}"')
        + f'<g stroke="{_rgb(CROP_MARK_RGB)}" stroke-width="{g.crop_mark_weight_pt}" stroke-linecap="butt" fill="none">'
        + marks
        + "</g></svg>"
    )


def _blank_html(page_count: int, g: PageGeometry) -> str:
    svg = _proof_svg(g)
    sheets = "\n".join(
        f'<section class="sheet">{svg}<p class="number">{n}</p></section>' for n in range(1, page_count + 1)
    )
    return f"""<!doctype html>
<html><head><meta charset="utf-8"><style>
@page {{
  size: {g.trim.width}pt {g.trim.height}pt; margin: 0;
  bleed: {g.trim.left - g.media.left}pt; marks: none;
}}
html, body {{ margin: 0; }}
.sheet {{ position: relative; width: {g.trim.width}pt; height: {g.trim.height}pt; break-after: page; }}
.sheet:last-child {{ break-after: auto; }}
.proof {{ position: absolute; left: {g.media.left - g.trim.left}pt; top: {g.trim.top - g.media.top}pt; }}
.number {{
  position: absolute; left: 0; right: 0; top: 50%; margin: 0; transform: translateY(-50%);
  text-align: center; font: 72pt "DejaVu Sans", "Arial", sans-serif; color: {_rgb(PROOF_TRIM_LINE_RGB)};
}}
</style></head><body>
{sheets}
</body></html>"""


def set_bleed_boxes(pdf, bleed: Box) -> None:
    """WeasyPrint finisher: give every page this BleedBox (see the module docstring for why).

    The BleedBox is changed in place: it is a pydyf Array, which a plain list could not replace.
    """
    for obj in pdf.objects:
        if isinstance(obj, dict) and obj.get("Type") == "/Page":
            obj["BleedBox"][:] = [bleed.left, bleed.bottom, bleed.right, bleed.top]
