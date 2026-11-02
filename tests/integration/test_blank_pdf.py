"""The blank print-geometry proof, rendered with WeasyPrint and read back with pypdf (boxes) and Ghostscript (pixels)."""
import pytest
from pypdf import PdfReader

from brochure.render.geometry import Box, page_geometry_pt
from brochure.render.pdf import render_blank_pdf

pytestmark = pytest.mark.integration

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
