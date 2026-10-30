"""The stub agents: fixed answers from sample/, no LLM calls."""
import json

import pytest

from brochure.contracts.images import ImageTag
from brochure.llm import FakeLLM
from brochure.contracts.qa import QAIssue
from brochure.pipeline.stubs import ScriptedQA, load_sample_data, stub_agents
from tests.support import ROOT, sample_state


@pytest.fixture
def llm():
    return FakeLLM({})


def test_vision_stub_returns_the_tags_of_the_12_sample_images(llm):
    tags = stub_agents().vision(sample_state(), llm)
    expected = [ImageTag.model_validate(t) for t in json.loads((ROOT / "sample" / "image_tags.json").read_text(encoding="utf-8"))]
    assert len(tags) == 12
    assert tags == expected
    assert llm.calls == []


def text_slots():
    return [s for s in load_sample_data().template.slots if s.type == "text"]


def test_copywriter_stub_writes_every_text_slot_within_its_char_budget(llm):
    copy = stub_agents().copywriter(sample_state(), llm)
    slots = text_slots()
    assert set(copy) == {s.id for s in slots}
    too_long = {s.id: len(copy[s.id]) for s in slots if len(copy[s.id]) > s.char_budget}
    assert too_long == {}
    assert all(copy[s.id].strip() for s in slots)
    assert llm.calls == []


def test_stub_copy_file_only_names_text_slots_and_fits_their_budgets():
    data = load_sample_data()
    budgets = {s.id: s.char_budget for s in text_slots()}
    assert data.copy, "sample/stub_copy.json is empty"
    assert set(data.copy) <= set(budgets)
    assert all(isinstance(v, str) and v.strip() for v in data.copy.values())
    assert {k: len(v) for k, v in data.copy.items() if len(v) > budgets[k]} == {}


def laid_out(llm):
    """The sample state after the copywriter, and the spec the layout stub makes from it."""
    agents = stub_agents()
    state = sample_state()
    state = state.model_copy(update={"slot_copy": agents.copywriter(state, llm), "image_tags": agents.vision(state, llm)})
    return state, agents.layout(state, llm)


def test_layout_stub_makes_8_pages_with_every_slot_of_the_template_filled_exactly_once(llm):
    _, spec = laid_out(llm)
    template = load_sample_data().template
    assert spec.template_id == "classic-8pp"
    assert len(spec.pages) == 8
    placed = sorted((n, slot_id) for n, page in enumerate(spec.pages, start=1) for slot_id in page.slots)
    assert placed == sorted((s.page, s.id) for s in template.slots)
    assert llm.calls == []


def slot_fills(spec):
    return {slot_id: fill for page in spec.pages for slot_id, fill in page.slots.items()}


def test_layout_stub_puts_each_manifest_image_in_its_intended_slot(llm):
    _, spec = laid_out(llm)
    fills = slot_fills(spec)
    manifest = load_sample_data().manifest
    assert len(manifest.images) == 12
    assert {e.intended_slot: fills[e.intended_slot].image_path for e in manifest.images} == {
        e.intended_slot: e.filename for e in manifest.images
    }


def test_layout_stub_uses_the_brand_kit_logo_in_both_logo_slots(llm):
    state, spec = laid_out(llm)
    fills = slot_fills(spec)
    assert fills["cover_logo"].image_path == state.brand_kit.logo_path
    assert fills["back_logo"].image_path == state.brand_kit.logo_path


def test_layout_stub_puts_the_copy_in_text_slots_and_the_rera_number_in_its_slot(llm):
    state, spec = laid_out(llm)
    fills = slot_fills(spec)
    text_ids = {s.id for s in text_slots()}
    assert {i: fills[i].text for i in text_ids} == {i: state.slot_copy[i] for i in text_ids}
    assert fills["rera_number"].text == state.project_facts.rera_number
    assert all(len(fills[s.id].text) <= s.char_budget for s in text_slots())


def test_layout_stub_sets_qr_data_for_the_rera_qr_slot(llm):
    _, spec = laid_out(llm)
    fill = slot_fills(spec)["rera_qr"]
    assert fill.qr_data and fill.qr_data.startswith("https://")


def test_renderer_stub_returns_8_clearly_fake_page_paths_and_creates_no_files(llm, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    state, spec = laid_out(llm)
    result = stub_agents().renderer(state.model_copy(update={"spec": spec}), llm)
    assert "FAKE" in result.pdf_path and result.pdf_path.endswith(".pdf")
    assert len(result.page_images) == 8
    assert all("FAKE" in p and p.endswith(".png") for p in result.page_images)
    assert len(set(result.page_images)) == 8
    assert list(tmp_path.iterdir()) == []


def issue(route_to, note="problem"):
    return QAIssue(check="stub", page=1, severity="error", note=note, route_to=route_to)


def test_qa_stub_reports_nothing_by_default(llm):
    assert stub_agents().qa(sample_state(), llm) == []


def test_qa_stub_reports_the_scripted_issues_for_the_current_round(llm):
    script = [[issue("copywriter", "first")], [issue("layout", "second"), issue("none", "third")]]
    qa = stub_agents(qa=ScriptedQA(script)).qa
    state = sample_state()
    assert [i.note for i in qa(state.model_copy(update={"qa_round": 0}), llm)] == ["first"]
    assert [i.note for i in qa(state.model_copy(update={"qa_round": 1}), llm)] == ["second", "third"]
    assert qa(state.model_copy(update={"qa_round": 2}), llm) == []


def test_export_stub_does_nothing_and_returns_nothing(llm, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    assert stub_agents().export(sample_state(), llm) is None
    assert list(tmp_path.iterdir()) == []
