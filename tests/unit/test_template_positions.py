"""templates/classic-8pp/positions.json: where each slot sits on its page, and the rules every position must keep."""
import json
from pathlib import Path

import pytest

from brochure.print_config import PRINT, PrintConfig
from brochure.render.positions import (
    CAPTION_HEIGHT_MM, CAPTION_WIDTH_MM, ROLES, BlockGap, Decoration, Rect, StaticText, block_gaps, caption_rect, drawn_rect,
    gap_problems, load_positions, position_problems, trim_rect,
)
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
    assert (banner.left, banner.top, banner.right, banner.bottom) == (-3, -3, 213, template.get("overview_img").height_mm)


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


# --- the caption of a captioned image ---------------------------------------------------------------------------------


def test_the_caption_box_sits_in_the_named_corner_inset_from_each_edge(tmp_path):
    template, places = write(tmp_path, [image("i", 100, 80), image("b", 210, 100, bleed=["top", "left", "right"], page=2)],
                             [at("i", 20, 20), at("b", 0, 0) | {"caption": "top-right"}])
    r = caption_rect(template.get("i"), places.of("i"))
    assert (r.right, r.bottom) == (117.5, 97.5)  # bottom right by default, 2.5 mm in from an edge that does not bleed
    assert (r.w, r.h) == (CAPTION_WIDTH_MM, CAPTION_HEIGHT_MM)
    r = caption_rect(template.get("b"), places.of("b"))
    assert (r.right, r.top) == (200, 10)  # on an edge that bleeds, the safe margin inside the trim


def test_a_caption_under_a_slot_listed_over_the_image_is_reported(tmp_path):
    slots = [image("i", 100, 100), text("t", 100, 10)]
    overlay = [{"slot": "t", "over": "i"}]
    found = problems(tmp_path, slots, [at("i", 20, 20), at("t", 20, 105, role="body")], overlay)
    assert found == ["the caption of 'i' lies under 't', which is listed over it; give 'i' another caption corner"]
    assert problems(tmp_path, slots, [at("i", 20, 20) | {"caption": "top-right"}, at("t", 20, 105, role="body")], overlay) == []


def test_a_caption_under_a_decoration_is_reported(tmp_path):
    band = {"id": "band", "pages": [1], "x_mm": 0, "y_mm": 100, "width_mm": 210, "height_mm": 30}
    template, places = write(tmp_path, [image("i", 100, 100)], [at("i", 20, 20)])
    places = places.model_copy(update={"decorations": [Decoration(**band)]})
    assert position_problems(places, template) == [
        "the caption of 'i' lies under the decoration 'band'; give 'i' another caption corner"]
    assert position_problems(places.model_copy(update={"decorations": [Decoration(**{**band, "pages": [2]})]}), template) == []


def test_a_caption_that_does_not_fit_inside_its_image_is_reported(tmp_path):
    assert problems(tmp_path, [image("i", 20, 50)], [at("i", 20, 20)]) == ["the caption of 'i' does not fit inside the image"]


def test_a_logo_has_no_caption_to_place(tmp_path):
    assert problems(tmp_path, [image("cover_logo", 20, 5)], [at("cover_logo", 20, 20)]) == []


def test_an_unknown_caption_corner_is_refused(tmp_path):
    with pytest.raises(ValueError, match="caption"):
        write(tmp_path, [image("i", 100, 100)], [at("i", 20, 20) | {"caption": "middle"}])


def test_the_cover_caption_is_top_right_of_the_hero_above_the_band_and_clear_of_the_logo(template, positions):
    r = caption_rect(template.get("hero"), positions.of("hero"))
    band = next(d for d in positions.decorations if d.id == "cover-band")
    assert positions.of("hero").caption == "top-right"
    assert r.right == 200 and r.top == 10 and r.bottom < band.y_mm
    assert not r.overlaps(trim_rect(template.get("cover_logo"), positions.of("cover_logo")))


# --- static template text ---------------------------------------------------------------------------------------------


def static(id="s", page=1, x=20, y=20, w=50, h=10, role="heading", text="Words"):
    return StaticText(id=id, page=page, x_mm=x, y_mm=y, width_mm=w, height_mm=h, role=role, text=text)


def with_static(tmp_path, *items):
    template, positions = write(tmp_path, [image("i", 50, 50)], [at("i", 20, 100)])
    return position_problems(positions.model_copy(update={"static_text": list(items)}), template)


def test_static_text_in_the_safe_area_clear_of_the_slots_keeps_the_rules(tmp_path):
    assert with_static(tmp_path, static()) == []


def test_static_text_outside_the_safe_area_is_reported(tmp_path):
    found = with_static(tmp_path, static(x=5))
    assert len(found) == 1 and "'s'" in found[0] and "safe area" in found[0]


def test_static_text_on_a_slot_or_on_other_static_text_is_reported(tmp_path):
    assert with_static(tmp_path, static(y=95)) == ["static text 's' overlaps 'i' on page 1"]
    assert with_static(tmp_path, static(id="a"), static(id="b", y=25)) == ["static text 'b' overlaps 'a' on page 1"]
    assert with_static(tmp_path, static(y=95, page=2)) == []


def test_static_text_with_an_unknown_role_is_reported(tmp_path):
    assert with_static(tmp_path, static(role="fancy")) == [f"static text 's' needs a role, one of {', '.join(ROLES)}; it has 'fancy'"]


@pytest.mark.parametrize("page, title", [(3, "Location"), (4, "Amenities"), (5, "Floor plans"), (6, "Specifications")])
def test_the_section_titles_are_headings_on_their_pages(positions, page, title):
    found = [s for s in positions.static_text if s.page == page and s.text == title]
    assert len(found) == 1 and found[0].role == "heading"


def test_the_qr_label_is_small_print_centred_under_the_qr_code(template, positions):
    labels = [s for s in positions.static_text if s.text == "Scan for RERA registration details"]
    assert len(labels) == 1
    label = labels[0]
    qr = trim_rect(template.get("rera_qr"), positions.of("rera_qr"))
    assert label.page == 8 and label.role == "small-print"
    assert qr.bottom <= label.y_mm <= qr.bottom + 3
    assert label.x_mm + label.width_mm / 2 == qr.x + qr.w / 2


# --- vertical spacing -------------------------------------------------------------------------------------------------


def test_the_block_gap_limit_is_in_the_print_config():
    assert PRINT.max_block_gap_mm == 15


def test_block_gaps_are_the_white_space_between_consecutive_blocks_on_a_page(tmp_path):
    template, places = write(tmp_path, [image("a", 50, 20), image("b", 50, 60), image("c", 50, 20), image("d", 50, 20, page=2)],
                             [at("a", 20, 20), at("b", 80, 20), at("c", 20, 100), at("d", 20, 20)])
    assert block_gaps(places, template) == [BlockGap(1, "b", "c", 20)]  # 'b' reaches lower than 'a'; 'd' is alone


def test_a_slot_drawn_on_an_image_is_not_a_block_of_its_own(tmp_path):
    template, places = write(tmp_path, [image("i", 100, 50), text("t", 50, 10), image("j", 100, 20)],
                             [at("i", 20, 20), at("t", 30, 30, role="body"), at("j", 20, 80)], [{"slot": "t", "over": "i"}])
    assert block_gaps(places, template) == [BlockGap(1, "i", "j", 10)]


def test_block_gaps_can_use_the_measured_height_of_the_text(tmp_path):
    template, places = write(tmp_path, [text("t", 50, 30), image("j", 100, 20)], [at("t", 20, 20, role="body"), at("j", 20, 60)])
    assert block_gaps(places, template) == [BlockGap(1, "t", "j", 10)]
    assert block_gaps(places, template, {"t": 12}) == [BlockGap(1, "t", "j", 28)]


def test_static_text_is_a_block(tmp_path):
    template, places = write(tmp_path, [image("j", 100, 20)], [at("j", 20, 60)])
    places = places.model_copy(update={"static_text": [static(y=20, h=10)]})
    assert block_gaps(places, template) == [BlockGap(1, "s", "j", 30)]


def test_gap_problems_report_a_gap_over_the_limit_unless_the_lower_block_is_exempt(tmp_path):
    template, places = write(tmp_path, [image("a", 50, 20), image("b", 50, 20)], [at("a", 20, 20), at("b", 20, 60)])
    assert gap_problems(places, template) == ["page 1: 20 mm between 'a' and 'b', the limit is 15 mm"]
    assert gap_problems(places, template, PrintConfig(max_block_gap_mm=20)) == []
    assert gap_problems(places.model_copy(update={"free_gap_above": ["b"]}), template) == []


def test_no_gap_on_the_classic_template_is_over_the_limit_but_the_one_above_the_disclaimer(template, positions):
    assert positions.free_gap_above == ["disclaimer"]
    assert gap_problems(positions, template) == []


def test_about_img_is_88_mm_wide(template):
    assert template.get("about_img").width_mm == 88
