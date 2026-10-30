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
