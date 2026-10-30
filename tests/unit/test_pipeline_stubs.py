"""The stub agents: fixed answers from sample/, no LLM calls."""
import json

import pytest

from brochure.contracts.images import ImageTag
from brochure.llm import FakeLLM
from brochure.pipeline.stubs import load_sample_data, stub_agents
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
