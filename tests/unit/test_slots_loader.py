import json

import pytest
from pydantic import ValidationError

from brochure.print_config import PrintConfig
from brochure.slots import load_slots

FULL_PAGE = {"id": "hero", "type": "image", "page": 1, "width_mm": 210, "height_mm": 297,
             "bleed_edges": ["top", "right", "bottom", "left"]}


def write_slots(tmp_path, *slots):
    path = tmp_path / "slots.json"
    path.write_text(json.dumps({"template_id": "t", "slots": list(slots)}), encoding="utf-8")
    return path


def test_loads_the_slots_in_file_order(tmp_path):
    inside = {**FULL_PAGE, "id": "photo", "bleed_edges": []}
    template = load_slots(write_slots(tmp_path, FULL_PAGE, inside))
    assert template.template_id == "t"
    assert [s.id for s in template.slots] == ["hero", "photo"]


def test_full_page_slot_with_all_four_bleed_edges_needs_2552_by_3579_px(tmp_path):
    hero = load_slots(write_slots(tmp_path, FULL_PAGE)).get("hero")
    assert hero.min_px == (2552, 3579)


def test_slot_inside_the_trim_needs_no_bleed_pixels(tmp_path):
    photo = {**FULL_PAGE, "id": "photo", "width_mm": 180, "height_mm": 120, "bleed_edges": []}
    assert load_slots(write_slots(tmp_path, photo)).get("photo").min_px == (2126, 1418)


def test_bleed_is_added_only_on_the_listed_edges(tmp_path):
    banner = {**FULL_PAGE, "id": "banner", "width_mm": 210, "height_mm": 120, "bleed_edges": ["top", "left", "right"]}
    slot = load_slots(write_slots(tmp_path, banner)).get("banner")
    assert (slot.bleed_width_mm, slot.bleed_height_mm) == (216, 123)
    assert slot.min_px == (2552, 1453)
