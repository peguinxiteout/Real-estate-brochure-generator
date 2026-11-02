"""The graph with the real Brief and Copywriter agents (a FakeLLM behind them) and the stubs for the other steps."""
import logging
import socket

import pytest

from brochure.llm import FakeLLM, LLMRateLimited
from brochure.pipeline import ScriptedQA, load_sample_data, real_agents
from brochure.verbatim import VERBATIM_SLOTS
from tests.support import GOOD_COPY, Run, qa_issue, sample_state
from tests.unit.test_agent_copywriter import Script

LOCATION = "Meridian Park Road, Pune"
CANNED = {
    "name": None, "rera_number": "P99999000000 (SAMPLE)", "rera_state": None, "location": None,
    "configurations": [{"label": "2 BHK", "carpet_area_sqft": 780}, {"label": "3 BHK", "carpet_area_sqft": 1090}],
    "amenities": [], "specifications": [], "landmarks": [], "possession": "December 2028",
    "tone_notes": "warm and aspirational, calm and confident",
}


@pytest.fixture(autouse=True)
def no_network(monkeypatch):
    def refuse(*args, **kwargs):
        raise AssertionError("a pipeline unit test tried to use the network")

    monkeypatch.setattr(socket.socket, "connect", refuse)
    monkeypatch.setattr(socket, "getaddrinfo", refuse)


def sparse_run(canned=CANNED):
    llm = FakeLLM({"brief.extract": canned, "copy.write": GOOD_COPY})  # the copywriter is real too: it needs a reply
    return Run(real_agents(), llm=llm), llm


def test_what_the_prompt_states_is_filled_and_only_the_unmentioned_field_is_asked():
    run, llm = sparse_run()
    run.start(sample_state(briefed=False, brief_file="brief_sparse.json"))
    assert run.paused_at == ("ask_user",)
    assert run.interrupt_value["missing_fields"] == ["location"]
    assert [c.task for c in llm.calls] == ["brief.extract"]  # paused at the question: the copywriter has not run


def test_answering_the_question_reaches_review_with_the_facts_the_prompt_stated():
    run, llm = sparse_run()
    run.start(sample_state(briefed=False, brief_file="brief_sparse.json"))
    run.resume({"location": LOCATION})
    assert run.paused_at == ("human_review",)
    facts = run.state.project_facts
    assert facts.rera_number == "P99999000000 (SAMPLE)"
    assert facts.possession == "December 2028"
    assert [c.label for c in facts.configurations] == ["2 BHK", "3 BHK"]
    assert facts.location == LOCATION
    assert facts.rera_state == "Maharashtra"  # from the form


def test_the_run_keeps_the_merged_form_so_the_question_loop_works_on_it():
    run, _ = sparse_run()
    run.start(sample_state(briefed=False, brief_file="brief_sparse.json"))
    form = run.state.brief.form
    assert form.rera_number == "P99999000000 (SAMPLE)"
    assert form.possession == "December 2028"
    assert run.state.brief.prompt  # the prompt itself is untouched


def test_when_the_model_fails_the_run_asks_for_everything_the_form_lacks_as_before(caplog):
    from brochure.llm import LLMRateLimited

    class Failing:
        calls = []

        def complete(self, task, payload, images=None):
            raise LLMRateLimited("rate limit still hit")

    run = Run(real_agents(), llm=Failing())
    run.start(sample_state(briefed=False, brief_file="brief_sparse.json"))
    assert run.paused_at == ("ask_user",)
    assert run.interrupt_value["missing_fields"] == ["rera_number", "location", "possession"]
    run.resume({"rera_number": "P1", "location": LOCATION, "possession": "Dec 2028"})
    assert run.paused_at == ("human_review",)


def test_every_step_but_brief_and_copywriter_is_still_a_stub_so_the_run_ends_after_approval():
    run, _ = sparse_run()
    run.start(sample_state(briefed=False, brief_file="brief_sparse.json"))
    run.resume({"location": LOCATION})
    assert len(run.state.image_tags) == 12 and len(run.state.spec.pages) == 8
    run.resume("approved")
    assert run.paused_at == ()
    assert run.state.approval_status == "approved"


def test_the_real_steps_use_the_llm_the_graph_hands_them_and_real_agents_takes_none():
    import inspect

    assert "llm" not in inspect.signature(real_agents).parameters
    run, llm = sparse_run()
    run.start(sample_state(briefed=False, brief_file="brief_sparse.json"))
    assert [c.task for c in llm.calls] == ["brief.extract"]  # paused at the question: the copywriter has not run


# --- the real Copywriter in the graph ----------------------------------------------------------------------------------


NOTHING_FOUND = {
    "name": None, "rera_number": None, "rera_state": None, "location": None, "configurations": [], "amenities": [],
    "specifications": [], "landmarks": [], "possession": None, "tone_notes": None,
}
TEXT_SLOTS = {s.id for s in load_sample_data().template.slots if s.type == "text"}


def full_run(copy_replies=(GOOD_COPY,), qa=None):
    """A run of the sample (complete brief) on the real Brief and Copywriter agents; returns (run, llm).

    The Script plays one answer per call in order: the brief step calls first, then the copywriter once per pass.
    """
    llm = Script(NOTHING_FOUND, *copy_replies)
    return Run(real_agents(qa=qa), llm=llm), llm


def test_the_graph_with_the_real_brief_and_copywriter_reaches_review_with_every_owned_slot_filled():
    run, llm = full_run()
    run.start(sample_state(briefed=False))
    assert run.paused_at == ("human_review",)
    assert [call[0] for call in llm.calls] == ["brief.extract", "copy.write"]
    state = run.state
    assert set(state.slot_copy) == TEXT_SLOTS
    for slot_id, text in GOOD_COPY.items():
        assert state.slot_copy[slot_id] == text
    fills = {sid: fill for page in state.spec.pages for sid, fill in page.slots.items()}
    assert {sid: fills[sid].text for sid in GOOD_COPY} == GOOD_COPY
    assert not any("[copy needed" in (f.text or "") for f in fills.values())


def test_legal_and_contact_text_comes_from_code_not_the_model():
    run, llm = full_run()
    run.start(sample_state(briefed=False))
    state = run.state
    brand = state.brand_kit
    assert state.slot_copy["disclaimer"] == brand.disclaimer
    assert state.slot_copy["about_text"] == brand.about_text
    assert state.slot_copy["rera_number"] == state.project_facts.rera_number
    sent = [slot["id"] for slot in llm.calls[1][1]["slots"]]
    assert not set(sent) & set(VERBATIM_SLOTS)
    assert set(sent) == TEXT_SLOTS - set(VERBATIM_SLOTS)


def test_when_the_model_cannot_be_used_the_run_still_reaches_review_with_placeholders_for_the_written_slots(caplog):
    llm = Script(NOTHING_FOUND, LLMRateLimited("rate limit"))
    run = Run(real_agents(), llm=llm)
    run.start(sample_state(briefed=False))
    assert run.paused_at == ("human_review",)
    fills = {sid: fill for page in run.state.spec.pages for sid, fill in page.slots.items()}
    assert fills["cover_tagline"].text == "[copy needed: cover_tagline]"
    assert fills["disclaimer"].text == run.state.brand_kit.disclaimer  # verbatim slots are unaffected
    assert len([r for r in caplog.records if r.levelno >= logging.WARNING]) == 1


def test_only_qa_issues_routed_to_the_copywriter_reach_it_and_a_second_pass_gets_them():
    issues = [qa_issue("copywriter", note="tagline repeats the headline"), qa_issue("layout", note="text overflows"), qa_issue("none")]
    run, llm = full_run(copy_replies=(GOOD_COPY, GOOD_COPY), qa=ScriptedQA([issues]))
    run.start(sample_state(briefed=False))
    assert run.paused_at == ("human_review",)
    copy_calls = [c for c in llm.calls if c[0] == "copy.write"]
    assert len(copy_calls) == 2
    assert "qa_issues" not in copy_calls[0][1]
    assert [i["note"] for i in copy_calls[1][1]["qa_issues"]] == ["tagline repeats the headline"]
