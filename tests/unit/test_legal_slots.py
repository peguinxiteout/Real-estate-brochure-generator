"""The template's legal slots, and which issues on them mean legal content is missing from the print file."""
import json
from pathlib import Path

import pytest

from brochure.contracts.qa import QAIssue
from brochure.contracts.spec import SlotFill
from brochure.legal import blocking_issues, load_legal_slots
from brochure.llm import FakeLLM
from brochure.pipeline.stubs import load_sample_data, stub_agents
from brochure.render.html import PX_PER_MM, text_overflow_issues
from tests.support import GOOD_COPY, sample_state

TEMPLATE = load_sample_data().template
LEGAL = ["cover_rera_line", "rera_number", "disclaimer", "rera_qr"]


@pytest.fixture
def spec():
    state = sample_state()
    return stub_agents().layout(state.model_copy(update={"slot_copy": stub_agents().copywriter(state, FakeLLM({}))}), FakeLLM({}))


def without(spec, slot_id):
    pages = [p.model_copy(deep=True) for p in spec.pages]
    for page in pages:
        page.slots.pop(slot_id, None)
    return spec.model_copy(update={"pages": pages})


def with_fill(spec, slot_id, fill):
    pages = [p.model_copy(deep=True) for p in spec.pages]
    page = TEMPLATE.get(slot_id).page - 1
    pages[page].slots[slot_id] = fill
    return spec.model_copy(update={"pages": pages})


def warned(spec, *issues):
    return spec.model_copy(update={"qa_warnings": [*spec.qa_warnings, *issues]})


def off_page(spec, slot_id):
    """The real overflow check's issue for a slot whose text ran off its page: start mark, no end mark."""
    slot = TEMPLATE.get(slot_id)
    anchors = [{} for _ in range(8)]
    for s in TEMPLATE.slots:
        if s.type == "text":
            anchors[s.page - 1][f"start-{s.id}"] = (0, 0, 0, 0)
            anchors[s.page - 1][f"end-{s.id}"] = (0, 1.0 * PX_PER_MM, 0, 0)
    del anchors[slot.page - 1][f"end-{slot_id}"]
    [issue] = text_overflow_issues(anchors, spec, TEMPLATE)
    return issue


def test_the_legal_slots_of_the_template_are_these():
    assert load_legal_slots("classic-8pp") == LEGAL


def test_the_legal_list_names_real_slots():
    assert set(load_legal_slots("classic-8pp")) <= {s.id for s in TEMPLATE.slots}


def test_the_legal_list_is_template_data_not_in_slots_json():
    folder = Path(__file__).parents[2] / "templates" / "classic-8pp"
    assert json.loads((folder / "legal_slots.json").read_text(encoding="utf-8"))["legal_slots"] == LEGAL
    assert "legal" not in (folder / "slots.json").read_text(encoding="utf-8")


def test_a_list_naming_an_unknown_slot_or_a_missing_file_is_refused(tmp_path):
    folder = tmp_path / "t"
    folder.mkdir()
    with pytest.raises(FileNotFoundError):
        load_legal_slots("t", tmp_path)
    (folder / "slots.json").write_text(json.dumps({"template_id": "t", "slots": [
        {"id": "a", "type": "text", "page": 1, "width_mm": 10, "height_mm": 10, "char_budget": 10}]}), encoding="utf-8")
    (folder / "legal_slots.json").write_text(json.dumps({"template_id": "t", "legal_slots": ["a", "zz"]}), encoding="utf-8")
    with pytest.raises(ValueError, match="zz"):
        load_legal_slots("t", tmp_path)


def test_a_complete_brochure_has_no_blocking_issues(spec):
    assert blocking_issues(spec, TEMPLATE, LEGAL) == []


@pytest.mark.parametrize("slot_id, page", [("cover_rera_line", 1), ("rera_number", 8), ("disclaimer", 8)])
def test_legal_text_that_ran_off_the_page_blocks(spec, slot_id, page):
    issue = off_page(spec, slot_id)
    assert blocking_issues(warned(spec, issue), TEMPLATE, LEGAL) == [issue]
    assert issue.page == page


def test_other_text_that_ran_off_the_page_does_not_block(spec):
    assert blocking_issues(warned(spec, off_page(spec, "amenities_list")), TEMPLATE, LEGAL) == []


def test_legal_text_merely_taller_than_its_slot_does_not_block(spec):
    tall = QAIssue(check="render.text_overflow", page=8, severity="warning", route_to="none",
                   note="disclaimer: the text is 25 mm tall but the slot is 18 mm; it is verbatim, so a person must change its source")
    assert blocking_issues(warned(spec, tall), TEMPLATE, LEGAL) == []


def test_verbatim_over_budget_on_a_legal_slot_does_not_block_because_nothing_is_missing(spec):
    over = QAIssue(check="verbatim.over_budget", page=8, severity="warning", route_to="none",
                   note="disclaimer: 600 characters, the budget is 500; the text is kept as it is")
    assert blocking_issues(warned(spec, over), TEMPLATE, LEGAL) == []


def test_another_checks_error_naming_a_legal_slot_does_not_block(spec):
    other = QAIssue(check="qa.spelling", page=8, severity="error", route_to="none", note="disclaimer: a spelling mistake")
    assert blocking_issues(warned(spec, other), TEMPLATE, LEGAL) == []


@pytest.mark.parametrize("slot_id, page", [("cover_rera_line", 1), ("rera_number", 8), ("disclaimer", 8), ("rera_qr", 8)])
def test_a_legal_slot_left_out_of_the_spec_blocks_on_its_page(spec, slot_id, page):
    [issue] = blocking_issues(without(spec, slot_id), TEMPLATE, LEGAL)
    assert (issue.check, issue.page, issue.severity, issue.route_to) == ("legal.slot_empty", page, "error", "none")
    assert issue.note.startswith(f"{slot_id}: ") and "missing from the print file" in issue.note


@pytest.mark.parametrize("fill", [SlotFill(image_path="a.jpg"), SlotFill(text=""), SlotFill(text="   \n ")], ids=["an image", "empty", "blank"])
def test_a_legal_text_slot_with_no_text_blocks(spec, fill):
    [issue] = blocking_issues(with_fill(spec, "disclaimer", fill), TEMPLATE, LEGAL)
    assert issue.check == "legal.slot_empty" and issue.note.startswith("disclaimer: ")


def test_a_legal_text_slot_showing_the_missing_copy_placeholder_blocks(spec):
    state = sample_state().model_copy(update={"slot_copy": GOOD_COPY})
    placeholder = stub_agents().layout(state, FakeLLM({}))
    assert "disclaimer" in {i.note.split(":")[0] for i in blocking_issues(placeholder, TEMPLATE, LEGAL)}


@pytest.mark.parametrize("fill", [SlotFill(text="not a code"), SlotFill(qr_data=""), SlotFill(qr_data="  ")], ids=["text", "empty", "blank"])
def test_a_qr_slot_with_no_qr_data_blocks(spec, fill):
    [issue] = blocking_issues(with_fill(spec, "rera_qr", fill), TEMPLATE, LEGAL)
    assert issue.check == "legal.slot_empty" and "rera_qr" in issue.note and "QR" in issue.note


def test_an_empty_slot_that_is_not_legal_does_not_block(spec):
    assert blocking_issues(without(spec, "cover_tagline"), TEMPLATE, LEGAL) == []


def test_several_blocking_issues_come_in_the_order_of_the_legal_list(spec):
    broken = warned(without(spec, "rera_qr"), off_page(spec, "disclaimer"))
    assert [i.note.split(":")[0] for i in blocking_issues(broken, TEMPLATE, LEGAL)] == ["disclaimer", "rera_qr"]
