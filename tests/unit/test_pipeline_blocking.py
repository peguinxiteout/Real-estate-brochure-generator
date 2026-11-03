"""The reviewer cannot approve a brochure whose legal text is missing from the PDF, and export never runs with it."""
from dataclasses import replace

import pytest
from langgraph.types import Command

from brochure.contracts.qa import QAIssue
from brochure.pipeline import RenderResult, ScriptedQA, sqlite_checkpointer, stub_agents
from tests.support import Run, counted

FAKE = RenderResult(pdf_path="x.pdf", page_images=[f"p{n}.png" for n in range(1, 9)])
NOTE = "disclaimer: the text runs off the page, so part of it is not printed but the slot is 18 mm; it is verbatim, so a person must change its source"
LOST = QAIssue(check="render.text_overflow", page=8, severity="error", note=NOTE, route_to="none")
BLOCKING = {"check": "render.text_overflow", "page": 8, "note": NOTE}


class Renderer:
    """Reports the issues in issues_per_pass[n] on pass n + 1; later passes report nothing."""

    def __init__(self, *issues_per_pass):
        self.issues_per_pass, self.passes = issues_per_pass, 0

    def __call__(self, state, llm):
        issues = self.issues_per_pass[self.passes] if self.passes < len(self.issues_per_pass) else []
        self.passes += 1
        return replace(FAKE, issues=list(issues))


def blocked_run(*issues_per_pass, qa=None):
    agents, calls = counted(replace(stub_agents(qa=qa), renderer=Renderer(*(issues_per_pass or ([LOST], [LOST], [LOST])))))
    run = Run(agents)
    run.start()
    return run, calls


def test_the_review_question_always_has_a_blocking_key_and_it_is_empty_when_nothing_is_missing():
    run, _ = blocked_run([])
    assert run.interrupt_value["blocking"] == [] and run.interrupt_value["error"] is None


def test_the_review_question_lists_what_blocks_approval_as_check_page_note():
    run, _ = blocked_run()
    assert run.paused_at == ("human_review",)
    assert run.interrupt_value["blocking"] == [BLOCKING] and run.interrupt_value["error"] is None


def test_approving_while_blocked_does_not_approve_and_asks_again_with_the_first_note():
    run, calls = blocked_run()
    run.resume("approved")
    assert run.paused_at == ("human_review",)
    assert run.state.approval_status != "approved"
    assert run.interrupt_value["error"] == f"can't approve: {NOTE}"
    assert run.interrupt_value["blocking"] == [BLOCKING]
    assert calls["export"] == 0


def test_approving_again_and_again_never_exports():
    run, calls = blocked_run()
    for _ in range(4):
        run.resume("approved")
    assert run.paused_at == ("human_review",) and calls["export"] == 0 and run.state.approval_status != "approved"


def test_a_bad_answer_while_blocked_still_gets_the_bad_answer_error_and_keeps_the_blocking_list():
    run, _ = blocked_run()
    run.resume("maybe")
    assert "not 'maybe'" in run.interrupt_value["error"] and run.interrupt_value["blocking"] == [BLOCKING]


def test_changes_requested_still_works_while_blocked():
    run, calls = blocked_run([LOST])
    run.resume("changes_requested")
    assert (calls["layout"], calls["renderer"], calls["qa"]) == (2, 2, 2)
    assert run.paused_at == ("human_review",)


def test_once_the_legal_text_is_back_the_run_can_be_approved_and_exported():
    run, calls = blocked_run([LOST])
    run.resume("approved")
    run.resume("changes_requested")
    assert run.interrupt_value["blocking"] == [] and run.interrupt_value["error"] is None
    run.resume("approved")
    assert run.paused_at == () and run.state.approval_status == "approved" and calls["export"] == 1


def test_changes_requested_after_a_refused_approval_that_is_still_blocked_stays_blocked():
    run, calls = blocked_run([LOST], [LOST])
    run.resume("changes_requested")
    assert run.interrupt_value["blocking"] == [BLOCKING]
    run.resume("approved")
    assert calls["export"] == 0 and "can't approve" in run.interrupt_value["error"]


def test_lost_text_outside_the_legal_slots_can_be_approved():
    other = LOST.model_copy(update={"note": "amenities_list: the text runs off the page", "page": 4})
    run, calls = blocked_run([other])
    assert run.interrupt_value["blocking"] == []
    run.resume("approved")
    assert calls["export"] == 1


def test_a_legal_slot_the_layout_left_empty_blocks_approval():
    agents = stub_agents()
    layout = agents.layout

    def losing_the_qr(state, llm):
        spec = layout(state, llm)
        pages = [p.model_copy(deep=True) for p in spec.pages]
        pages[7].slots.pop("rera_qr")
        return spec.model_copy(update={"pages": pages})

    agents, calls = counted(replace(agents, layout=losing_the_qr))
    run = Run(agents)
    run.start()
    [item] = run.interrupt_value["blocking"]
    assert (item["check"], item["page"]) == ("legal.slot_empty", 8) and set(item) == {"check", "page", "note"}
    run.resume("approved")
    assert calls["export"] == 0 and item["note"] in run.interrupt_value["error"]


def test_a_qa_step_that_forgets_the_lost_text_cannot_unblock_approval():
    run, calls = blocked_run(qa=lambda state, llm: [])
    assert run.interrupt_value["blocking"] == [BLOCKING]
    run.resume("approved")
    assert calls["export"] == 0


def test_lost_text_is_reported_once_when_the_qa_step_passes_it_through():
    run, _ = blocked_run(qa=ScriptedQA())
    assert run.interrupt_value["blocking"] == [BLOCKING]
    assert [w.note for w in run.state.spec.qa_warnings].count(NOTE) == 1


def test_forcing_the_graph_to_export_while_blocked_raises_before_the_export_runs():
    run, calls = blocked_run()
    with pytest.raises(RuntimeError, match="can't export"):
        run.graph.invoke(Command(goto="export", update={"approval_status": "approved"}), run.config)
    assert calls["export"] == 0


def test_a_blocked_review_survives_a_restart(tmp_path):
    agents = replace(stub_agents(), renderer=Renderer([LOST]))
    first_saver = sqlite_checkpointer(tmp_path / "c.sqlite")
    Run(agents, checkpointer=first_saver).start()
    first_saver.conn.close()

    second_saver = sqlite_checkpointer(tmp_path / "c.sqlite")
    run = Run(agents, checkpointer=second_saver)
    assert run.interrupt_value["blocking"] == [BLOCKING]
    run.resume("approved")
    assert "can't approve" in run.interrupt_value["error"]
    second_saver.conn.close()
