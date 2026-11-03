"""The rule-based Layout step in the pipeline: no LLM, the assigned images in the spec, its findings shown to the reviewer."""
import socket
from pathlib import Path

import pytest

from brochure.layout import LOGO_SLOTS, assign_images, load_layout_rules
from brochure.llm import FakeLLM
from brochure.pipeline import ScriptedQA, load_sample_data, real_agents, stub_agents
from brochure.verbatim import verbatim_copy
from tests.support import GOOD_COPY, STUB_RENDERER, Run, qa_issue, sample_state
from tests.unit.test_pipeline_real_agents import NOTHING_FOUND

ROOT = Path(__file__).parents[2]
DATA = load_sample_data()
RULES = load_layout_rules(ROOT / "templates" / "classic-8pp" / "layout_rules.json")
UNFILLED = {"plan_img_b": 5, "amenity_img_c": 4, "about_img": 7}


@pytest.fixture(autouse=True)
def no_network(monkeypatch):
    def refuse(*args, **kwargs):
        raise AssertionError("a pipeline unit test tried to use the network")

    monkeypatch.setattr(socket.socket, "connect", refuse)
    monkeypatch.setattr(socket, "getaddrinfo", refuse)


def state_before_layout():
    state = sample_state()
    copy = {**verbatim_copy(state.project_facts, state.brand_kit), **GOOD_COPY}
    return state.model_copy(update={"image_tags": DATA.image_tags, "slot_copy": copy})


def fills(spec):
    return {slot_id: fill for page in spec.pages for slot_id, fill in page.slots.items()}


def test_the_real_layout_step_makes_no_llm_call():
    llm = FakeLLM({})
    real_agents().layout(state_before_layout(), llm)
    assert llm.calls == []


def test_the_real_layout_places_the_assigned_images_and_leaves_unfilled_slots_out_of_their_page():
    spec = real_agents().layout(state_before_layout(), FakeLLM({}))
    expected = assign_images(DATA.template, RULES, DATA.image_tags)
    placed = fills(spec)
    assert {s: placed[s].image_path for s in expected.placements} == {s: p.image for s, p in expected.placements.items()}
    for slot_id, page in UNFILLED.items():
        assert slot_id not in spec.pages[page - 1].slots
    assert len(spec.pages) == 8


def test_the_real_layouts_findings_are_the_specs_qa_warnings():
    spec = real_agents().layout(state_before_layout(), FakeLLM({}))
    assert spec.qa_warnings == assign_images(DATA.template, RULES, DATA.image_tags).findings
    assert len(spec.qa_warnings) == 7 and all(w.route_to == "none" for w in spec.qa_warnings)
    severity = {w.check: w.severity for w in spec.qa_warnings}
    assert severity == {"layout.slot_unfilled": "error", "layout.dpi_warn": "warning", "layout.image_unused": "warning"}


def test_text_logos_and_the_qr_are_filled_exactly_as_the_stub_fills_them():
    state = state_before_layout()
    real, stub = fills(real_agents().layout(state, FakeLLM({}))), fills(stub_agents().layout(state, FakeLLM({})))
    kept = {s.id for s in DATA.template.slots if s.type in ("text", "qr") or s.id in LOGO_SLOTS}
    assert {s: real[s] for s in kept} == {s: stub[s] for s in kept}


def test_the_stub_layout_still_places_every_image_in_its_intended_slot_with_no_warnings():
    spec = stub_agents().layout(state_before_layout(), FakeLLM({}))
    intended = {e.intended_slot: e.filename for e in DATA.manifest.images}
    assert {s: fills(spec)[s].image_path for s in intended} == intended
    assert spec.qa_warnings == []


def full_run(qa=None):
    llm = FakeLLM({"brief.extract": NOTHING_FOUND, "copy.write": GOOD_COPY})
    run = Run(real_agents(qa=qa, renderer=STUB_RENDERER), llm=llm)
    run.start(sample_state(briefed=False))
    return run, llm


def test_the_graph_with_real_agents_reaches_review_with_the_layouts_warnings():
    run, llm = full_run()
    assert run.paused_at == ("human_review",)
    assert {c.task for c in llm.calls} == {"brief.extract", "copy.write"}  # the layout called nothing
    warnings = run.state.spec.qa_warnings
    assert sorted({w.check for w in warnings}) == ["layout.dpi_warn", "layout.image_unused", "layout.slot_unfilled"]
    assert any("floorplan_3bhk.jpg is 207 DPI" in w.note for w in warnings)


def test_a_qa_issue_routed_to_layout_reruns_the_same_deterministic_layout():
    run, _ = full_run(qa=ScriptedQA([[qa_issue("layout", note="move the pool picture")]]))
    assert run.paused_at == ("human_review",)
    first_pass = real_agents().layout(run.state, FakeLLM({}))
    assert run.state.spec.pages == first_pass.pages  # the instruction is not acted on yet: chat edits come later
    assert run.state.spec.qa_warnings == first_pass.qa_warnings


def test_the_layouts_warnings_survive_a_qa_pass_whose_issues_go_to_the_reviewer():
    run, _ = full_run(qa=ScriptedQA([[qa_issue("none", note="cosmetic")]]))
    notes = [w.note for w in run.state.spec.qa_warnings]
    assert "cosmetic" in notes
    assert any(n.startswith("plan_img_b: ") for n in notes), notes
