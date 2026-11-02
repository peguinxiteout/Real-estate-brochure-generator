"""The blank print-geometry proof, rendered with WeasyPrint and read back with pypdf (boxes) and Ghostscript (pixels)."""
import subprocess
import sys
from pathlib import Path

import pytest
from PIL import Image
from pypdf import PdfReader

from brochure.print_config import PRINT
from brochure.render.geometry import Box, mm_to_pt, page_geometry_pt
from brochure.render.pdf import PROOF_FILL_RGB, render_blank_pdf

pytestmark = pytest.mark.integration

ROOT = Path(__file__).parents[2]
PAGES = 8
TOL_PT = 0.01


@pytest.fixture
def blank_pdf(weasyprint_module, tmp_path):
    return render_blank_pdf(PAGES, tmp_path / "blank.pdf")


def test_has_the_requested_number_of_pages(blank_pdf):
    assert len(PdfReader(blank_pdf).pages) == PAGES


def as_box(pdf_box) -> Box:
    return Box(*(float(v) for v in (pdf_box.left, pdf_box.bottom, pdf_box.right, pdf_box.top)))


def assert_box(actual: Box, expected: Box, name: str, page: int):
    for side in ("left", "bottom", "right", "top"):
        assert getattr(actual, side) == pytest.approx(getattr(expected, side), abs=TOL_PT), (name, page, side, actual)


def test_every_page_has_the_media_bleed_and_trim_boxes_of_the_geometry(blank_pdf):
    g = page_geometry_pt()
    for n, page in enumerate(PdfReader(blank_pdf).pages, start=1):
        assert_box(as_box(page.mediabox), g.media, "MediaBox", n)
        assert_box(as_box(page.bleedbox), g.bleed, "BleedBox", n)
        assert_box(as_box(page.trimbox), g.trim, "TrimBox", n)


def test_every_page_has_its_boxes_nested(blank_pdf):
    for page in PdfReader(blank_pdf).pages:
        media, bleed, trim = as_box(page.mediabox), as_box(page.bleedbox), as_box(page.trimbox)
        assert media.contains(bleed) and bleed.contains(trim)
        assert media != bleed != trim


# --- Raster checks: page 1 rendered by Ghostscript (found the way `brochure doctor` finds it), read with Pillow ---

DPI = 100
PX_PER_PT = DPI / 72


def white(rgb) -> bool:
    return min(rgb) >= 245


def dark(rgb) -> bool:
    return max(rgb) < 100


class Raster:
    """Page 1 as pixels, addressed in PDF points (the geometry's coordinates). Rows run down from the MediaBox top."""

    def __init__(self, image: Image.Image, media: Box):
        self.image, self.media, self.pixels = image, media, image.load()

    def at(self, x_pt: float, y_pt: float):
        return self.pixels[self.col(x_pt), self.row(y_pt)]

    def col(self, x_pt: float) -> int:
        return int((x_pt - self.media.left) * PX_PER_PT)

    def row(self, y_pt: float) -> int:
        return int((self.media.top - y_pt) * PX_PER_PT)

    def pixel_rect(self, box: Box, grow_px: int = 0) -> tuple[int, int, int, int]:
        """Columns and rows [c0, c1) x [r0, r1) covering box, grown by grow_px, clipped to the image."""
        w, h = self.image.size
        return (max(0, self.col(box.left) - grow_px), max(0, self.row(box.top) - grow_px),
                min(w, self.col(box.right) + 1 + grow_px), min(h, self.row(box.bottom) + 1 + grow_px))


def inside(rect, c, r) -> bool:
    c0, r0, c1, r1 = rect
    return c0 <= c < c1 and r0 <= r < r1


@pytest.fixture
def page1(blank_pdf, ghostscript_exe, tmp_path) -> Raster:
    png = tmp_path / "page1.png"
    result = subprocess.run(
        [str(ghostscript_exe), "-dSAFER", "-dBATCH", "-dNOPAUSE", "-dQUIET", "-sDEVICE=png16m", f"-r{DPI}",
         "-dFirstPage=1", "-dLastPage=1", f"-sOutputFile={png}", str(blank_pdf)],
        capture_output=True, text=True, timeout=120,
    )
    assert result.returncode == 0, result.stderr
    image = Image.open(png).convert("RGB")
    media = page_geometry_pt().media
    assert image.size == (round(media.width * PX_PER_PT), round(media.height * PX_PER_PT))  # Ghostscript drew the MediaBox
    return Raster(image, media)


def test_the_full_bleed_colour_reaches_the_bleed_edge(page1):
    b = page_geometry_pt().bleed
    inset = 1.5 / PX_PER_PT  # one and a half pixels inside the bleed box
    mid_x, mid_y = (b.left + b.right) / 2, (b.bottom + b.top) / 2
    points = {
        "left": (b.left + inset, mid_y), "right": (b.right - inset, mid_y),
        "bottom": (mid_x, b.bottom + inset), "top": (mid_x, b.top - inset),
        "bottom-left": (b.left + inset, b.bottom + inset), "top-right": (b.right - inset, b.top - inset),
    }
    for name, (x, y) in points.items():
        rgb = page1.at(x, y)
        assert all(abs(a - e) <= 6 for a, e in zip(rgb, PROOF_FILL_RGB)), (name, rgb)


def test_between_the_bleed_edge_and_the_crop_marks_is_white(page1):
    g = page_geometry_pt()
    inner = page1.pixel_rect(g.bleed, grow_px=1)
    outer = page1.pixel_rect(g.trim.grown(mm_to_pt(PRINT.crop_mark_offset_mm)), grow_px=-2)
    c0, r0, c1, r1 = outer
    not_white = [(c, r) for r in range(r0, r1) for c in range(c0, c1)
                 if not inside(inner, c, r) and not white(page1.pixels[c, r])]
    assert not_white == []


def test_crop_marks_are_dark_lines_with_white_beside_them(page1):
    g = page_geometry_pt()
    for m in g.crop_marks:
        for t in (0.2, 0.5, 0.8):  # along the mark
            x, y = m.x0 + t * (m.x1 - m.x0), m.y0 + t * (m.y1 - m.y0)
            c, r = page1.col(x), page1.row(y)
            across = [(c, r + d) for d in (-1, 0, 1)] if m.y0 == m.y1 else [(c + d, r) for d in (-1, 0, 1)]
            beside = [(c, r + d) for d in (-4, 4)] if m.y0 == m.y1 else [(c + d, r) for d in (-4, 4)]
            assert any(dark(page1.pixels[p]) for p in across), (m, t, [page1.pixels[p] for p in across])
            assert all(white(page1.pixels[p]) for p in beside), (m, t, [page1.pixels[p] for p in beside])


def test_make_blank_pdf_script_writes_an_8_page_pdf_to_the_path_given(weasyprint_module, tmp_path):
    out = tmp_path / "proof.pdf"
    result = subprocess.run([sys.executable, str(ROOT / "tools" / "make_blank_pdf.py"), "--out", str(out)],
                            capture_output=True, text=True, timeout=120)
    assert result.returncode == 0, result.stderr
    assert out.is_file(), f"no PDF at {out}; stdout: {result.stdout}"
    assert len(PdfReader(out).pages) == 8
    assert str(out) in result.stdout


def test_nothing_dark_in_the_slug_except_the_crop_marks(page1):
    g = page_geometry_pt()
    w, h = page1.image.size
    bleed = page1.pixel_rect(g.bleed, grow_px=1)
    marks = [page1.pixel_rect(m.bounds, grow_px=3) for m in g.crop_marks]
    dark_pixels = [(c, r) for r in range(h) for c in range(w)
                   if not inside(bleed, c, r) and dark(page1.pixels[c, r]) and not any(inside(k, c, r) for k in marks)]
    assert dark_pixels == []
