"""The pipeline graph on stub agents: the whole flow runs with no LLM and no rendering."""
import socket
from dataclasses import replace

import pytest


from brochure.pipeline import ScriptedQA, load_sample_data, sqlite_checkpointer, stub_agents
from tests.support import Run, counted, qa_issue, sample_state


@pytest.fixture(autouse=True)
def pipeline_guards(monkeypatch):
    """Every test here: no network, and the FakeLLM of every Run must end with zero calls (the stubs never call a model)."""

    def refuse(*args, **kwargs):
        raise AssertionError("a pipeline unit test tried to use the network")

    monkeypatch.setattr(socket.socket, "connect", refuse)
    monkeypatch.setattr(socket, "getaddrinfo", refuse)
    Run.created.clear()
    yield
    assert [run.llm.calls for run in Run.created] == [[] for _ in Run.created]


def test_a_full_run_pauses_at_review_with_an_8_page_spec_and_ends_after_approval():
    run = Run()
    run.start()
    assert run.paused_at == ("human_review",)
    state = run.state
    assert state.project_facts.name == "Aurelia Heights"
    assert len(state.image_tags) == 12
    assert len(state.spec.pages) == 8
    assert len(state.page_images) == 8
    assert state.pdf_path

    run.resume("approved")
    assert run.paused_at == ()
    assert run.state.approval_status == "approved"
    assert run.llm.calls == []


def test_copywriter_starts_only_after_both_brief_and_vision_have_finished():
    order = []

    def spy(name, real):
        def agent(state, llm):
            order.append(name)
            return real(state, llm)

        return agent

    stubs = stub_agents()
    agents = replace(stubs, brief=spy("brief", stubs.brief), vision=spy("vision", stubs.vision),
                     copywriter=spy("copywriter", stubs.copywriter))
    Run(agents).start()
    assert sorted(order[:2]) == ["brief", "vision"]
    assert order[2:] == ["copywriter"]


def test_a_missing_rera_number_pauses_the_run_and_resuming_with_it_continues():
    run = Run()
    run.start(sample_state(briefed=False, rera_number=None))
    assert run.paused_at == ("ask_user",)
    assert run.state.missing_fields == ["rera_number"]
    assert run.state.project_facts is None
    assert run.state.slot_copy == {}  # the copywriter has not started

    run.resume({"rera_number": "P99999000001"})
    assert run.paused_at == ("human_review",)
    assert run.state.missing_fields == []
    assert run.state.project_facts.rera_number == "P99999000001"
    assert run.state.brief.form.rera_number == "P99999000001"
    assert run.llm.calls == []


def run_with_qa(script):
    agents, counts = counted(stub_agents(qa=ScriptedQA(script)))
    run = Run(agents)
    run.start()
    return run, counts


def test_a_copywriter_issue_sends_the_run_back_through_copy_layout_render_and_qa():
    run, calls = run_with_qa([[qa_issue("copywriter")]])
    assert run.paused_at == ("human_review",)
    assert (calls["copywriter"], calls["layout"], calls["renderer"], calls["qa"]) == (2, 2, 2, 2)
    assert run.state.qa_round == 2
    assert run.state.qa_issues == []
    assert run.state.spec.qa_warnings == []


def test_a_layout_issue_sends_the_run_back_to_layout_without_rewriting_the_copy():
    run, calls = run_with_qa([[qa_issue("layout")]])
    assert run.paused_at == ("human_review",)
    assert (calls["copywriter"], calls["layout"], calls["renderer"], calls["qa"]) == (1, 2, 2, 2)
    assert run.state.qa_round == 2


def test_an_issue_routed_to_none_does_not_loop_and_is_kept_as_a_warning_on_the_spec():
    run, calls = run_with_qa([[qa_issue("none", "cosmetic")]])
    assert run.paused_at == ("human_review",)
    assert (calls["copywriter"], calls["layout"], calls["renderer"], calls["qa"]) == (1, 1, 1, 1)
    assert run.state.qa_round == 1
    assert [i.note for i in run.state.spec.qa_warnings] == ["cosmetic"]


def test_after_3_qa_rounds_the_run_moves_on_and_the_remaining_issues_become_spec_warnings():
    always = [[qa_issue("copywriter", f"round {n}")] for n in range(1, 6)]
    run, calls = run_with_qa(always)
    assert run.paused_at == ("human_review",)
    assert (calls["copywriter"], calls["layout"], calls["renderer"], calls["qa"]) == (3, 3, 3, 3)
    assert run.state.qa_round == 3
    assert [i.note for i in run.state.spec.qa_warnings] == ["round 3"]


def test_when_a_pass_reports_copywriter_and_layout_issues_the_earlier_step_runs_first():
    run, calls = run_with_qa([[qa_issue("layout"), qa_issue("copywriter")]])
    assert (calls["copywriter"], calls["layout"], calls["qa"]) == (2, 2, 2)


def test_a_pass_with_no_issues_goes_straight_to_review_with_no_warnings():
    run, calls = run_with_qa([])
    assert calls["qa"] == 1 and run.state.qa_round == 1
    assert run.state.spec.qa_warnings == []


def test_export_runs_only_after_approval():
    agents, calls = counted(stub_agents())
    run = Run(agents)
    run.start()
    assert calls["export"] == 0
    run.resume("approved")
    assert calls["export"] == 1


def test_changes_requested_loops_through_layout_render_and_qa_and_back_to_review():
    agents, calls = counted(stub_agents())
    run = Run(agents)
    run.start()
    run.resume("changes_requested")
    assert run.paused_at == ("human_review",)
    assert (calls["copywriter"], calls["layout"], calls["renderer"], calls["qa"], calls["export"]) == (1, 2, 2, 2, 0)
    assert run.state.approval_status == "pending"
    assert run.state.qa_round == 1  # each round of human changes gets a fresh QA budget

    run.resume("approved")
    assert run.paused_at == ()
    assert (run.state.approval_status, calls["export"]) == ("approved", 1)


def test_an_unknown_review_answer_is_asked_again_and_the_run_stays_at_review():
    run = Run()
    run.start()
    run.resume("maybe")
    assert run.paused_at == ("human_review",)
    assert "approved" in run.interrupt_value["error"]
    run.resume("approved")
    assert run.paused_at == ()
    assert run.state.approval_status == "approved"


def test_a_spy_agent_replaces_one_stub_and_the_other_stubs_still_work():
    seen = []

    def spy_copywriter(state, llm):
        seen.append(state.project_facts.name)
        return {slot.id: "SPY" for slot in load_sample_data().template.slots if slot.type == "text"}

    agents, calls = counted(replace(stub_agents(), copywriter=spy_copywriter))
    run = Run(agents)
    run.start()

    assert seen == ["Aurelia Heights"]
    assert run.paused_at == ("human_review",)
    cover_title = run.state.spec.pages[0].slots["cover_title"]
    assert cover_title.text == "SPY"
    assert (calls["layout"], calls["renderer"], calls["qa"]) == (1, 1, 1)
    assert len(run.state.spec.pages) == 8


def test_a_run_paused_at_review_resumes_from_sqlite_in_a_new_graph_and_connection(tmp_path):
    database = tmp_path / "pipeline.sqlite"

    first_saver = sqlite_checkpointer(database)
    first = Run(checkpointer=first_saver, thread_id="aurelia")
    first.start()
    assert first.paused_at == ("human_review",)
    first_saver.conn.close()

    second_saver = sqlite_checkpointer(database)
    second = Run(checkpointer=second_saver, thread_id="aurelia")  # new graph object, new connection, same file
    assert second.paused_at == ("human_review",)
    assert len(second.state.spec.pages) == 8
    second.resume("approved")
    assert second.paused_at == ()
    assert second.state.approval_status == "approved"
    second_saver.conn.close()
    assert first.llm.calls == [] and second.llm.calls == []


def test_the_pipeline_tests_cannot_open_a_network_connection():
    with pytest.raises(AssertionError, match="network"):
        socket.create_connection(("127.0.0.1", 9))  # the discard port: nothing listens, nothing leaves this machine


def missing_rera_run():
    run = Run()
    run.start(sample_state(briefed=False, rera_number=None))
    return run


def test_the_first_missing_fields_question_has_an_empty_errors_dict():
    assert missing_rera_run().interrupt_value == {"ask": "brief", "missing_fields": ["rera_number"], "errors": {}}


def test_an_unknown_field_in_the_answer_is_reported_and_asked_again():
    run = missing_rera_run()
    run.resume({"rera_numbr": "P99999000001"})
    assert run.paused_at == ("ask_user",)
    assert run.interrupt_value == {
        "ask": "brief",
        "missing_fields": ["rera_number"],
        "errors": {"rera_numbr": "unknown field"},
    }
