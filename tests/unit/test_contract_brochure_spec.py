import pytest
from pydantic import ValidationError

from brochure.contracts.spec import BrochureSpec


def page_data(n):
    return {
        "layout_id": f"page-{n}",
        "slots": {
            "title": {"text": f"Page {n}"},
            "hero": {"image_path": "hero_tower.jpg"},
        },
    }


def spec_data(page_count=8, **overrides):
    data = {
        "template_id": "classic-8pp",
        "pages": [page_data(n) for n in range(1, page_count + 1)],
        "qa_warnings": [
            {"check": "dpi", "page": 1, "severity": "warning", "note": "hero is 288 DPI", "route_to": "layout"}
        ],
        "version": 3,
    }
    data.update(overrides)
    return data


def test_valid_spec_parses():
    spec = BrochureSpec.model_validate(spec_data())
    assert spec.template_id == "classic-8pp"
    assert len(spec.pages) == 8
    assert spec.pages[0].slots["title"].text == "Page 1"
    assert spec.pages[0].slots["hero"].image_path == "hero_tower.jpg"
    assert spec.qa_warnings[0].route_to == "layout"
    assert spec.version == 3


@pytest.mark.parametrize("count", [0, 1, 6, 7, 9])
def test_page_count_not_a_multiple_of_four_is_rejected(count):
    with pytest.raises(ValidationError, match="multiple of 4"):
        BrochureSpec.model_validate(spec_data(page_count=count))


@pytest.mark.parametrize("count", [4, 8, 12])
def test_page_count_multiple_of_four_is_accepted(count):
    assert len(BrochureSpec.model_validate(spec_data(page_count=count)).pages) == count
