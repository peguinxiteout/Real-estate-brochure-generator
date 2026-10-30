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


def test_min_px_stored_in_the_file_is_rejected_because_the_loader_computes_it():
    with pytest.raises(ValidationError, match="min_px"):
        Slot.model_validate(slot_data(min_px=[2552, 3579]))


def test_text_slot_needs_a_char_budget():
    with pytest.raises(ValidationError, match="char_budget"):
        Slot.model_validate(slot_data(id="title", type="text", bleed_edges=[]))


def test_only_text_slots_may_have_a_char_budget():
    with pytest.raises(ValidationError, match="char_budget"):
        Slot.model_validate(slot_data(char_budget=40))


def test_unknown_bleed_edge_is_rejected():
    with pytest.raises(ValidationError, match="top"):
        Slot.model_validate(slot_data(bleed_edges=["middle"]))


def test_a_bleed_edge_listed_twice_is_rejected():
    with pytest.raises(ValidationError, match="more than once"):
        Slot.model_validate(slot_data(bleed_edges=["top", "top"]))


@pytest.mark.parametrize("width", [0, -5])
def test_width_mm_must_be_positive(width):
    with pytest.raises(ValidationError, match="width_mm"):
        Slot.model_validate(slot_data(width_mm=width))
