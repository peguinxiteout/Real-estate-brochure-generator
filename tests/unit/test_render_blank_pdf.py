"""render_blank_pdf without WeasyPrint: what it checks before it renders anything."""
import sys

import pytest

from brochure.render.pdf import render_blank_pdf


@pytest.mark.parametrize("page_count", [0, 6, 10])
def test_an_invalid_page_count_is_refused_before_weasyprint_is_imported(page_count, tmp_path, monkeypatch):
    monkeypatch.setitem(sys.modules, "weasyprint", None)  # importing it now raises ImportError
    out = tmp_path / "blank.pdf"
    with pytest.raises(ValueError, match="page count must be a positive multiple of 4"):
        render_blank_pdf(page_count, out)
    assert not out.exists()
