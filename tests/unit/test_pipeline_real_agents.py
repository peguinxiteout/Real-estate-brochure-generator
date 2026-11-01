"""The graph with the real Brief agent (a FakeLLM behind it) and the stubs for the other steps."""
import socket

import pytest

from brochure.llm import FakeLLM
from brochure.pipeline import real_agents
from tests.support import Run, sample_state

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
    llm = FakeLLM({"brief.extract": canned})
    return Run(real_agents(llm), llm=llm), llm


def test_what_the_prompt_states_is_filled_and_only_the_unmentioned_field_is_asked():
    run, llm = sparse_run()
    run.start(sample_state(briefed=False, brief_file="brief_sparse.json"))
    assert run.paused_at == ("ask_user",)
    assert run.interrupt_value["missing_fields"] == ["location"]
    assert [c.task for c in llm.calls] == ["brief.extract"]


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
