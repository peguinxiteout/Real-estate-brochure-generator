"""The blank print-geometry proof, rendered with WeasyPrint and read back with pypdf (boxes) and Ghostscript (pixels)."""
import pytest
from pypdf import PdfReader

from brochure.render.pdf import render_blank_pdf

pytestmark = pytest.mark.integration

PAGES = 8


@pytest.fixture
def blank_pdf(weasyprint_module, tmp_path):
    return render_blank_pdf(PAGES, tmp_path / "blank.pdf")


def test_has_the_requested_number_of_pages(blank_pdf):
    assert len(PdfReader(blank_pdf).pages) == PAGES
