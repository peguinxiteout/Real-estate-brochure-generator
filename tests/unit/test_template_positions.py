"""templates/classic-8pp/positions.json: where each slot sits on its page, and the rules every position must keep."""
import json
from pathlib import Path

import pytest

from brochure.print_config import PRINT, PrintConfig
from brochure.render.positions import ROLES, Rect, drawn_rect, load_positions, position_problems, trim_rect
from brochure.slots import load_slots

ROOT = Path(__file__).parents[2]
TEMPLATE = ROOT / "templates" / "classic-8pp"


@pytest.fixture(scope="module")
def template():
    return load_slots(TEMPLATE / "slots.json")


@pytest.fixture(scope="module")
def positions():
    return load_positions(TEMPLATE / "positions.json")


def test_safe_margin_is_in_the_print_config_and_starts_at_10_mm():
    assert PRINT.safe_margin_mm == 10


def test_the_classic_template_positions_keep_every_rule(template, positions):
    assert position_problems(positions, template) == []


def test_every_slot_has_exactly_one_position_and_every_position_names_a_slot(template, positions):
    named = [p.slot for p in positions.positions]
    assert sorted(named) == sorted(s.id for s in template.slots)


def test_text_slots_have_a_role_and_other_slots_none(template, positions):
    roles = {p.slot: p.role for p in positions.positions}
    for slot in template.slots:
        if slot.type == "text":
            assert roles[slot.id] in ROLES, slot.id
        else:
            assert roles[slot.id] is None, slot.id


def test_only_text_and_logos_lie_on_the_cover_hero(positions):
    assert sorted((o.slot, o.over) for o in positions.overlays) == [
        ("cover_logo", "hero"), ("cover_rera_line", "hero"), ("cover_tagline", "hero"), ("cover_title", "hero"),
    ]


def test_a_bleeding_slot_is_drawn_exactly_the_bleed_past_the_trim_on_each_listed_edge(template, positions):
    pos = {p.slot: p for p in positions.positions}
    hero = drawn_rect(template.get("hero"), pos["hero"])
    assert (hero.left, hero.top, hero.right, hero.bottom) == (-3, -3, 213, 300)
    banner = drawn_rect(template.get("overview_img"), pos["overview_img"])
    assert (banner.left, banner.top, banner.right, banner.bottom) == (-3, -3, 213, 120)


def test_a_slot_without_bleed_is_drawn_at_its_trim_side_size(template, positions):
    pos = {p.slot: p for p in positions.positions}
    slot = template.get("location_map")
    assert drawn_rect(slot, pos["location_map"]) == trim_rect(slot, pos["location_map"])
    assert trim_rect(slot, pos["location_map"]) == Rect(pos["location_map"].x_mm, pos["location_map"].y_mm, 180, 120)


# --- each rule, on a small template written for the test ------------------------------------------------------------


def write(tmp_path, slots, positions, overlays=()):
    (tmp_path / "slots.json").write_text(json.dumps({"template_id": "t", "slots": slots}), encoding="utf-8")
    (tmp_path / "positions.json").write_text(
        json.dumps({"template_id": "t", "positions": positions, "overlays": list(overlays)}), encoding="utf-8"
    )
    return load_slots(tmp_path / "slots.json"), load_positions(tmp_path / "positions.json")


def image(id, w, h, bleed=(), page=1):
    return {"id": id, "type": "image", "page": page, "width_mm": w, "height_mm": h, "bleed_edges": list(bleed)}


def text(id, w, h, page=1):
    return {"id": id, "type": "text", "page": page, "width_mm": w, "height_mm": h, "char_budget": 10}


def at(slot, x, y, role=None):
    return {"slot": slot, "x_mm": x, "y_mm": y, **({"role": role} if role else {})}


def problems(tmp_path, slots, positions, overlays=()):
    template, places = write(tmp_path, slots, positions, overlays)
    return position_problems(places, template)


def test_a_slot_with_no_position_and_a_position_with_no_slot_are_reported(tmp_path):
    found = problems(tmp_path, [image("a", 50, 50), image("b", 50, 50)], [at("a", 20, 20), at("zz", 20, 100)])
    assert any("'b'" in p and "no position" in p for p in found)
    assert any("'zz'" in p and "not a slot" in p for p in found)


def test_a_slot_positioned_twice_is_reported(tmp_path):
    found = problems(tmp_path, [image("a", 50, 50)], [at("a", 20, 20), at("a", 20, 100)])
    assert any("'a'" in p and "2 positions" in p for p in found)


def test_a_text_slot_without_a_known_role_and_an_image_with_a_role_are_reported(tmp_path):
    found = problems(tmp_path, [text("t", 50, 10), image("i", 50, 50)], [at("t", 20, 20), at("i", 20, 100, role="body")])
    assert any("'t'" in p and "role" in p for p in found)
    assert any("'i'" in p and "role" in p for p in found)
    found = problems(tmp_path, [text("t", 50, 10)], [at("t", 20, 20, role="fancy")])
    assert any("'t'" in p and "fancy" in p for p in found)


def test_a_listed_bleed_edge_must_lie_on_the_trim_edge(tmp_path):
    found = problems(tmp_path, [image("b", 100, 50, bleed=["left", "top"])], [at("b", 1, 0)])
    assert found == ["'b' bleeds off the left edge, so its left edge must be on the trim (x = 0), not 1 mm"]
    found = problems(tmp_path, [image("b", 100, 50, bleed=["right", "bottom"])], [at("b", 110, 240)])
    assert found == ["'b' bleeds off the bottom edge, so its bottom edge must be on the trim (297 mm), not 290 mm"]


def test_an_edge_not_listed_must_not_touch_the_trim_edge(tmp_path):
    found = problems(tmp_path, [image("b", 100, 50, bleed=["top"])], [at("b", 0, 0)])
    assert found == ["'b' does not bleed off the left edge, so it must lie inside the trim there (x = 0 mm)"]


def test_a_slot_without_bleed_must_lie_inside_the_trim(tmp_path):
    found = problems(tmp_path, [image("i", 100, 50)], [at("i", 150, 20)])
    assert found == ["'i' does not bleed off the right edge, so it must lie inside the trim there (right = 250 mm)"]


def test_text_and_qr_slots_must_lie_inside_the_safe_area(tmp_path):
    qr = {"id": "q", "type": "qr", "page": 1, "width_mm": 25, "height_mm": 25}
    found = problems(tmp_path, [text("t", 50, 10), qr], [at("t", 9, 20, role="body"), at("q", 180, 100)])
    assert any("'t'" in p and "safe area" in p for p in found)
    assert any("'q'" in p and "safe area" in p for p in found)
    found = problems(tmp_path, [image("i", 50, 50)], [at("i", 5, 5)])  # an image may sit in the margin
    assert found == []


def test_the_safe_margin_comes_from_the_print_config(tmp_path):
    template, positions = write(tmp_path, [text("t", 50, 10)], [at("t", 12, 20, role="body")])
    assert position_problems(positions, template) == []
    assert any("safe area" in p for p in position_problems(positions, template, PrintConfig(safe_margin_mm=15)))


def test_two_slots_overlapping_on_a_page_are_reported_unless_listed(tmp_path):
    slots = [image("i", 100, 100), text("t", 50, 10), image("other", 50, 50, page=2)]
    places = [at("i", 20, 20), at("t", 30, 30, role="body"), at("other", 30, 30)]
    assert problems(tmp_path, slots, places) == ["'i' and 't' overlap on page 1 and are not listed in overlays"]
    assert problems(tmp_path, slots, places, [{"slot": "t", "over": "i"}]) == []


def test_touching_slots_do_not_overlap(tmp_path):
    assert problems(tmp_path, [image("a", 50, 50), image("b", 50, 50)], [at("a", 20, 20), at("b", 70, 20)]) == []


def test_only_text_qr_or_a_logo_may_be_listed_over_an_image(tmp_path):
    slots = [image("a", 100, 100), image("b", 50, 50), text("t", 50, 10)]
    places = [at("a", 20, 20), at("b", 30, 30), at("t", 30, 90, role="body")]
    found = problems(tmp_path, slots, places, [{"slot": "b", "over": "a"}, {"slot": "t", "over": "a"}])
    assert found == ["overlay 'b' over 'a': only a text, QR or logo slot may lie on an image slot",
                     "'a' and 'b' overlap on page 1 and are not listed in overlays"]  # a refused entry excuses nothing
    slots = [text("t", 50, 10), text("u", 50, 10)]
    found = problems(tmp_path, slots, [at("t", 30, 30, role="body"), at("u", 30, 32, role="body")], [{"slot": "t", "over": "u"}])
    assert found == ["overlay 't' over 'u': only a text, QR or logo slot may lie on an image slot",
                     "'t' and 'u' overlap on page 1 and are not listed in overlays"]


def test_a_listed_overlay_that_does_not_overlap_is_reported(tmp_path):
    slots = [image("a", 50, 50), text("t", 50, 10)]
    found = problems(tmp_path, slots, [at("a", 20, 20), at("t", 20, 100, role="body")], [{"slot": "t", "over": "a"}])
    assert found == ["overlay 't' over 'a': they do not overlap, so the entry is not needed"]


def test_positions_for_another_template_are_reported(tmp_path):
    template, positions = write(tmp_path, [image("a", 50, 50)], [at("a", 20, 20)])
    found = position_problems(positions.model_copy(update={"template_id": "other"}), template)
    assert found == ["the positions are for template 'other', not 't'"]
