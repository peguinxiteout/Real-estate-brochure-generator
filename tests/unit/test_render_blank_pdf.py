"""render_blank_pdf without WeasyPrint: what it checks before it renders anything."""
import sys
from types import SimpleNamespace

import pytest

from brochure.render.geometry import Box
from brochure.render.pdf import render_blank_pdf, set_bleed_boxes


@pytest.mark.parametrize("page_count", [0, 6, 10])
def test_an_invalid_page_count_is_refused_before_weasyprint_is_imported(page_count, tmp_path, monkeypatch):
    monkeypatch.setitem(sys.modules, "weasyprint", None)  # importing it now raises ImportError
    out = tmp_path / "blank.pdf"
    with pytest.raises(ValueError, match="page count must be a positive multiple of 4"):
        render_blank_pdf(page_count, out)
    assert not out.exists()


def test_the_finisher_sets_every_page_bleed_box_in_place_and_leaves_other_objects_alone():
    # Stand-ins for pydyf's objects: a Dictionary is a dict and an Array is a list. The BleedBox must stay the same
    # list object, because WeasyPrint serialises pydyf Arrays and a plain list would not serialise.
    capped = [-10.0, -10.0, 605.28, 851.89]
    pages = [{"Type": "/Page", "BleedBox": capped}, {"Type": "/Page", "BleedBox": list(capped)}]
    catalog = {"Type": "/Catalog"}
    pdf = SimpleNamespace(objects=[catalog, pages[0], b"a content stream", pages[1]])
    first_box = pages[0]["BleedBox"]

    set_bleed_boxes(pdf, Box(-8.5, -8.5, 603.78, 850.39))

    assert [p["BleedBox"] for p in pages] == [[-8.5, -8.5, 603.78, 850.39]] * 2
    assert pages[0]["BleedBox"] is first_box
    assert catalog == {"Type": "/Catalog"}
