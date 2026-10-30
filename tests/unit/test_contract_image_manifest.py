import pytest
from pydantic import ValidationError

from brochure.contracts.manifest import ImageManifest


def entry(**overrides):
    data = {"filename": "hero_tower.jpg", "width_px": 2600, "height_px": 3650, "kind": "render", "intended_slot": "hero"}
    data.update(overrides)
    return data


def test_valid_manifest_parses():
    manifest = ImageManifest.model_validate({"images": [entry(), entry(filename="b.jpg", intended_slot="overview_img")]})
    assert [e.filename for e in manifest.images] == ["hero_tower.jpg", "b.jpg"]
    assert manifest.images[0].kind == "render"
    assert manifest.images[0].intended_slot == "hero"


def test_zero_width_px_is_rejected():
    with pytest.raises(ValidationError, match="greater than 0"):
        ImageManifest.model_validate({"images": [entry(width_px=0)]})
