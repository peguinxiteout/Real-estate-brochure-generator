import pytest
from pydantic import ValidationError

from brochure.contracts.slots import Slot


def slot_data(**overrides):
    data = {
        "id": "hero",
        "type": "image",
        "page": 1,
        "width_mm": 210,
        "height_mm": 297,
        "bleed_edges": ["top", "right", "bottom", "left"],
    }
    data.update(overrides)
    return data


def test_valid_image_slot_parses():
    slot = Slot.model_validate(slot_data())
    assert (slot.id, slot.type, slot.page) == ("hero", "image", 1)
    assert (slot.width_mm, slot.height_mm) == (210, 297)
    assert slot.bleed_edges == ["top", "right", "bottom", "left"]
    assert slot.char_budget is None
    assert slot.comment == ""


def test_bleed_edges_default_to_none_for_slots_inside_the_trim():
    data = slot_data()
    del data["bleed_edges"]
    assert Slot.model_validate(data).bleed_edges == []
