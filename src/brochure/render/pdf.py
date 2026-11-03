"""PDF output with WeasyPrint: the brochure (render_brochure) and a blank proof of the print geometry (render_blank_pdf).

What WeasyPrint (checked on 70.0) writes for `@page { size: W H; bleed: B; marks: crop }`:
- MediaBox = the page box grown by the CSS `bleed` on every edge; TrimBox = the page box, origin at its lower-left.
- BleedBox = the TrimBox grown by min(B, 10 pt). Its "bleed" is the whole area outside the trim, so with B = bleed +
  slug (13 mm) its BleedBox lands 10 pt (3.53 mm) outside the trim, not 3 mm.
- `marks: crop` draws 1 px (0.75 pt) lines from the MediaBox edge in to B / 2 from it, and only on a page with a
  background. Neither the weight nor the position can be set.

So the CSS bleed is set to bleed + slug (giving the right MediaBox), WeasyPrint's marks are off, the crop marks are
drawn here as vector lines from the geometry, and a finisher rewrites each page's BleedBox to the 3 mm bleed. Both
PDFs use the same page rule (page_css), crop marks (crop_marks_svg) and finisher (set_bleed_boxes).
"""
import json
import logging
import subprocess
from pathlib import Path

from brochure.contracts.brand import BrandKit
from brochure.contracts.images import ImageTag
from brochure.contracts.qa import QAIssue
from brochure.contracts.spec import BrochureSpec
from brochure.print_config import PRINT, PrintConfig
from brochure.render.geometry import Box, PageGeometry, check_page_count, page_geometry_pt

log = logging.getLogger(__name__)

PROOF_FILL_RGB = (214, 230, 245)  # light blue, fills the bleed box of the blank proof
PROOF_TRIM_LINE_RGB = (90, 110, 130)
PROOF_TRIM_LINE_PT = 0.5
CROP_MARK_RGB = (0, 0, 0)
PAGE_PNG_DPI = 100  # page images for review and the QA critic; not a print resolution
ISSUES_FILE = "render_issues.json"


def render_blank_pdf(page_count: int, path: Path, config: PrintConfig = PRINT) -> Path:
    """Write a blank proof of the print geometry: page_count pages, each with the page boxes and crop marks, a
    light-coloured fill over the bleed box, a thin rectangle on the trim line and its page number in the middle.

    The page number is set in a system sans-serif font: the proof is about geometry, not the brand fonts.
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


def page_css(g: PageGeometry) -> str:
    """The @page rule: trim-sized pages with no margin, and a CSS bleed of bleed + slug so the MediaBox is right."""
    return (f"@page {{ size: {g.trim.width}pt {g.trim.height}pt; margin: 0; "
            f"bleed: {g.trim.left - g.media.left}pt; marks: none; }}")


def media_svg(g: PageGeometry, inner: str, css_class: str) -> str:
    """An SVG over the whole MediaBox, in points, y downwards from its top-left corner. Place it with media_svg_css."""
    return (
        f'<svg class="{css_class}" xmlns="http://www.w3.org/2000/svg" width="{g.media.width}pt" '
        f'height="{g.media.height}pt" viewBox="0 0 {g.media.width} {g.media.height}">{inner}</svg>'
    )


def media_svg_css(g: PageGeometry, css_class: str) -> str:
    """Puts a media_svg over the MediaBox of a trim-sized, position: relative sheet."""
    return (f".{css_class} {{ position: absolute; left: {g.media.left - g.trim.left}pt; "
            f"top: {g.trim.top - g.media.top}pt; }}")


def _x(g: PageGeometry, v: float) -> float:
    return v - g.media.left


def _y(g: PageGeometry, v: float) -> float:
    return g.media.top - v


def _marks(g: PageGeometry) -> str:
    lines = "".join(
        f'<line x1="{_x(g, m.x0)}" y1="{_y(g, m.y0)}" x2="{_x(g, m.x1)}" y2="{_y(g, m.y1)}"/>' for m in g.crop_marks
    )
    return (f'<g stroke="{_rgb(CROP_MARK_RGB)}" stroke-width="{g.crop_mark_weight_pt}" stroke-linecap="butt" '
            f'fill="none">{lines}</g>')


def crop_marks_svg(g: PageGeometry, css_class: str = "crop-marks") -> str:
    """The crop marks of the geometry as vector lines, over the MediaBox."""
    return media_svg(g, _marks(g), css_class)


def _proof_svg(g: PageGeometry) -> str:
    def rect(box: Box, attrs: str) -> str:
        return f'<rect x="{_x(g, box.left)}" y="{_y(g, box.top)}" width="{box.width}" height="{box.height}" {attrs}/>'

    return media_svg(
        g,
        rect(g.bleed, f'fill="{_rgb(PROOF_FILL_RGB)}" stroke="none"')
        + rect(g.trim, f'fill="none" stroke="{_rgb(PROOF_TRIM_LINE_RGB)}" stroke-width="{PROOF_TRIM_LINE_PT}"')
        + _marks(g),
        "proof",
    )


def _blank_html(page_count: int, g: PageGeometry) -> str:
    svg = _proof_svg(g)
    sheets = "\n".join(
        f'<section class="sheet">{svg}<p class="number">{n}</p></section>' for n in range(1, page_count + 1)
    )
    return f"""<!doctype html>
<html><head><meta charset="utf-8"><style>
{page_css(g)}
html, body {{ margin: 0; }}
.sheet {{ position: relative; width: {g.trim.width}pt; height: {g.trim.height}pt; break-after: page; }}
.sheet:last-child {{ break-after: auto; }}
{media_svg_css(g, "proof")}
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


# --- the brochure ------------------------------------------------------------------------------------------------------


def _missing_images(spec: BrochureSpec, image_dir: Path) -> list[str]:
    from brochure.layout import LOGO_SLOTS  # the logos come from the brand kit, which has its own fallback

    return sorted({
        fill.image_path for page in spec.pages for slot_id, fill in page.slots.items()
        if fill.image_path is not None and slot_id not in LOGO_SLOTS and not (image_dir / fill.image_path).is_file()
    })


def render_brochure(
    spec: BrochureSpec, brand_kit: BrandKit, image_tags: list[ImageTag], image_dir: Path, out_dir: Path, *,
    brand_dir: Path | None = None, config: PrintConfig = PRINT,
) -> tuple[Path, list[Path]]:
    """Render the spec to out_dir/brochure.pdf and one PNG per page (out_dir/page-<n>.png, 100 DPI, cropped to the
    trim), in page order. Returns (pdf_path, page_image_paths); render_with_issues also returns the issues found."""
    pdf_path, pngs, _ = render_with_issues(spec, brand_kit, image_tags, image_dir, out_dir, brand_dir=brand_dir,
                                           config=config)
    return pdf_path, pngs


def render_with_issues(
    spec: BrochureSpec, brand_kit: BrandKit, image_tags: list[ImageTag], image_dir: Path, out_dir: Path, *,
    brand_dir: Path | None = None, config: PrintConfig = PRINT,
) -> tuple[Path, list[Path], list[QAIssue]]:
    """As render_brochure, plus the render's issues: text taller than its slot, measured on the laid-out pages, as
    render.text_overflow warnings for the copywriter. They are also written to out_dir/render_issues.json (an empty
    list when there are none) and logged. brand_dir is where a relative logo_path is looked up (default: the current
    directory)."""
    from brochure.render.html import build_html, load_template, text_overflow_issues

    image_dir = Path(image_dir).resolve()
    missing = _missing_images(spec, image_dir)
    if missing:
        raise FileNotFoundError(f"images not found in {image_dir}: {', '.join(missing)}")
    template = load_template(spec.template_id)
    check_page_count(len(spec.pages), config)
    html = build_html(spec, brand_kit, image_tags, image_dir, brand_dir=brand_dir, config=config)

    from weasyprint import HTML  # imported here so the checks above, and the unit tests, work without Pango

    document = HTML(string=html, base_url=str(template.directory)).render()
    if len(document.pages) != len(spec.pages):
        raise RuntimeError(f"the spec has {len(spec.pages)} pages but WeasyPrint laid out {len(document.pages)}")
    issues = text_overflow_issues([p.anchors for p in document.pages], spec, template.slots, config)

    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    pdf_path = out_dir / "brochure.pdf"
    bleed = page_geometry_pt(config).bleed
    document.write_pdf(pdf_path, finisher=lambda _document, pdf: set_bleed_boxes(pdf, bleed))
    (out_dir / ISSUES_FILE).write_text(json.dumps([i.model_dump() for i in issues], indent=2), encoding="utf-8")
    for issue in issues:
        log.warning("%s (page %s): %s", issue.check, issue.page, issue.note)
    return pdf_path, page_pngs(pdf_path, out_dir, len(spec.pages)), issues


def page_pngs(pdf_path: Path, out_dir: Path, page_count: int, dpi: int = PAGE_PNG_DPI) -> list[Path]:
    """Rasterise every page of the PDF with Ghostscript (found as `brochure doctor` finds it) to out_dir/page-<n>.png,
    cropped to the TrimBox: the page as it is after cutting, with no bleed, slug or crop marks."""
    from brochure.doctor import find_ghostscript

    gs = find_ghostscript().path
    if gs is None:
        raise RuntimeError("Ghostscript not found (looked at GS_BIN, PATH, C:\\Program Files\\gs); run `brochure doctor`")
    for old in out_dir.glob("page-*.png"):
        old.unlink()
    result = subprocess.run(
        [str(gs), "-dSAFER", "-dBATCH", "-dNOPAUSE", "-dQUIET", "-sDEVICE=png16m", f"-r{dpi}", "-dUseTrimBox",
         "-dTextAlphaBits=4", "-dGraphicsAlphaBits=4", f"-sOutputFile={out_dir / 'page-%d.png'}", str(pdf_path)],
        capture_output=True, text=True, timeout=300,
    )
    if result.returncode != 0:
        raise RuntimeError(f"Ghostscript failed ({result.returncode}): {result.stderr.strip()}")
    pngs = [out_dir / f"page-{n}.png" for n in range(1, page_count + 1)]
    absent = [p.name for p in pngs if not p.is_file()]
    if absent:
        raise RuntimeError(f"Ghostscript did not write {', '.join(absent)}")
    return pngs
