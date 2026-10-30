import pytest
from pydantic import ValidationError

from brochure.contracts.images import ImageTag


def tag_data(**overrides):
    data = {
        "path": "hero_tower.jpg",
        "kind": "render",
        "subject": "Tower facade at dusk",
        "width_px": 2600,
        "height_px": 3650,
        "quality": "good",
        "features": ["tower", "sky"],
        "focal_point": {"x": 0.5, "y": 0.4},
    }
    data.update(overrides)
    return data


def test_valid_image_tag_parses_and_round_trips_through_json():
    tag = ImageTag.model_validate(tag_data())
    assert tag.kind == "render"
    assert (tag.focal_point.x, tag.focal_point.y) == (0.5, 0.4)
    assert ImageTag.model_validate_json(tag.model_dump_json()) == tag


def test_focal_point_outside_0_to_1_is_rejected():
    with pytest.raises(ValidationError):
        ImageTag.model_validate(tag_data(focal_point={"x": 1.2, "y": 0.5}))


def test_zero_width_px_is_rejected():
    with pytest.raises(ValidationError):
        ImageTag.model_validate(tag_data(width_px=0))


def test_zero_height_px_is_rejected():
    with pytest.raises(ValidationError):
        ImageTag.model_validate(tag_data(height_px=0))
