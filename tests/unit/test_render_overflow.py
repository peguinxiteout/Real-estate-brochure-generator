"""Text overflow, measured from the start and end marks of each text slot (WeasyPrint's public Page.anchors), and the
renderer's checks that run before WeasyPrint is imported."""
import math

import pytest

from brochure.contracts.spec import BrochureSpec, PageSpec, SlotFill
from brochure.pipeline.stubs import load_sample_data
from brochure.verbatim import VERBATIM_SLOTS
from brochure.render.html import PX_PER_MM, text_heights, text_overflow_issues
from brochure.render.pdf import render_brochure
from tests.support import sample_state

TEMPLATE = load_sample_data().template
INTRO_MM = TEMPLATE.get("overview_intro").height_mm


def anchors(slot_id: str, height_mm: float, top_px: float = 100.0) -> dict:
    """The two marks of one slot, as Page.anchors gives them: (x, y, ...) in CSS px."""
    return {f"start-{slot_id}": (50.0, top_px, 0, 0), f"end-{slot_id}": (50.0, top_px + height_mm * PX_PER_MM, 0, 0)}


def spec_with(page2: dict[str, SlotFill]) -> BrochureSpec:
    pages = [PageSpec(layout_id=f"p{n}", slots=page2 if n == 2 else {}) for n in range(1, 9)]
    return BrochureSpec(template_id="classic-8pp", pages=pages)


def test_text_within_its_slot_height_is_not_reported():
    spec = spec_with({"overview_intro": SlotFill(text="x")})
    pages = [{} for _ in range(8)]
    pages[1] = anchors("overview_intro", INTRO_MM)
    assert text_overflow_issues(pages, spec, TEMPLATE) == []


def test_text_taller_than_its_slot_is_a_warning_for_the_copywriter_on_its_page():
    spec = spec_with({"overview_intro": SlotFill(text="x"), "overview_headline": SlotFill(text="y")})
    pages = [{} for _ in range(8)]
    pages[1] = {**anchors("overview_intro", INTRO_MM + 12.4), **anchors("overview_headline", 9, top_px=600)}
    issues = text_overflow_issues(pages, spec, TEMPLATE)
    assert len(issues) == 1
    issue = issues[0]
    assert (issue.check, issue.page, issue.severity, issue.route_to) == ("render.text_overflow", 2, "warning", "copywriter")
    assert "overview_intro" in issue.note and f"{INTRO_MM + 12.4:.0f} mm" in issue.note and f"{INTRO_MM:g} mm" in issue.note


def test_a_fraction_of_a_millimetre_over_is_rounding_not_overflow():
    spec = spec_with({"overview_intro": SlotFill(text="x")})
    pages = [{} for _ in range(8)]
    pages[1] = anchors("overview_intro", INTRO_MM + 0.3)
    assert text_overflow_issues(pages, spec, TEMPLATE) == []


def test_text_heights_gives_the_measured_height_of_each_filled_text_slot():
    spec = spec_with({"overview_intro": SlotFill(text="x"), "overview_img": SlotFill(image_path="a.jpg")})
    pages = [{} for _ in range(8)]
    pages[1] = anchors("overview_intro", 16.5)
    assert text_heights(pages, spec, TEMPLATE) == {"overview_intro": pytest.approx(16.5)}


def only_start(slot_id: str) -> dict:
    """What a page has for a slot whose text ran off it: the start mark, and no end mark."""
    return {f"start-{slot_id}": (50.0, 100.0, 0, 0)}


def page_with(number: int, anchors_of_page: dict) -> list[dict]:
    pages = [{} for _ in range(8)]
    pages[number - 1] = anchors_of_page
    return pages


def spec_on(number: int, slot_id: str) -> BrochureSpec:
    pages = [PageSpec(layout_id=f"p{n}", slots={slot_id: SlotFill(text="x")} if n == number else {}) for n in range(1, 9)]
    return BrochureSpec(template_id="classic-8pp", pages=pages)


def test_text_that_ran_off_the_page_measures_infinitely_tall():
    heights = text_heights(page_with(2, only_start("overview_intro")), spec_on(2, "overview_intro"), TEMPLATE)
    assert heights == {"overview_intro": math.inf}


def test_copywriter_text_that_ran_off_the_page_is_an_issue_for_the_copywriter_not_a_crash():
    [issue] = text_overflow_issues(page_with(2, only_start("overview_intro")), spec_on(2, "overview_intro"), TEMPLATE)
    assert (issue.check, issue.page, issue.route_to) == ("render.text_overflow", 2, "copywriter")
    assert "overview_intro" in issue.note and "runs off the page" in issue.note and "not printed" in issue.note


def test_verbatim_text_that_ran_off_the_page_is_an_issue_for_nobody_not_a_crash():
    [issue] = text_overflow_issues(page_with(4, only_start("amenities_list")), spec_on(4, "amenities_list"), TEMPLATE)
    assert (issue.check, issue.page, issue.route_to) == ("render.text_overflow", 4, "none")
    assert "amenities_list" in issue.note and "runs off the page" in issue.note


def test_text_lost_off_the_page_is_an_error_and_text_merely_over_its_slot_a_warning():
    lost = text_overflow_issues(page_with(4, only_start("amenities_list")), spec_on(4, "amenities_list"), TEMPLATE)
    tall = text_overflow_issues(page_with(4, anchors("amenities_list", 500)), spec_on(4, "amenities_list"), TEMPLATE)
    assert [i.severity for i in lost] == ["error"] and [i.severity for i in tall] == ["warning"]


@pytest.mark.parametrize("slot_id", [s.id for s in TEMPLATE.slots if s.type == "text"])
def test_every_text_slot_routes_its_overflow_by_who_owns_the_text(slot_id):
    slot = TEMPLATE.get(slot_id)
    [issue] = text_overflow_issues(page_with(slot.page, anchors(slot_id, slot.height_mm + 5)), spec_on(slot.page, slot_id), TEMPLATE)
    assert issue.route_to == ("none" if slot_id in VERBATIM_SLOTS else "copywriter")


def test_only_the_copywriter_is_told_to_shorten_it():
    tall = lambda slot_id, page: text_overflow_issues(page_with(page, anchors(slot_id, 500)), spec_on(page, slot_id), TEMPLATE)[0]
    assert "shorten it" in tall("overview_intro", 2).note
    verbatim = tall("config_table", 5).note
    assert "shorten it" not in verbatim and "verbatim" in verbatim


def test_a_text_slot_without_its_marks_is_an_error_in_the_renderer():
    spec = spec_with({"overview_intro": SlotFill(text="x")})
    with pytest.raises(RuntimeError, match="overview_intro"):
        text_overflow_issues([{} for _ in range(8)], spec, TEMPLATE)


def test_render_brochure_refuses_missing_image_files_before_rendering(tmp_path):
    state = sample_state()
    spec = spec_with({"overview_img": SlotFill(image_path="nowhere.jpg")})
    with pytest.raises(FileNotFoundError, match="nowhere.jpg"):
        render_brochure(spec, state.brand_kit, [], tmp_path, tmp_path / "out")
    assert not (tmp_path / "out").exists()
