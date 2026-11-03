"""Issues the renderer finds (text overflow) reach the QA step and loop like any QA issue."""
from dataclasses import replace
from pathlib import Path

from brochure.contracts.qa import QAIssue
from brochure.llm import FakeLLM
from brochure.pipeline import RenderResult, ScriptedQA, stub_agents
from brochure.pipeline.real import RealRenderer
from brochure.pipeline.stubs import REPO_ROOT
from tests.support import Run, counted, qa_issue, sample_state

FAKE = RenderResult(pdf_path="x.pdf", page_images=[f"p{n}.png" for n in range(1, 9)])


def overflow(note="overview_intro: the text is 82 mm tall but the slot is 70 mm; shorten it"):
    return QAIssue(check="render.text_overflow", page=2, severity="warning", note=note, route_to="copywriter")


class ScriptedRenderer:
    """issues_per_pass[n] is what the renderer reports on its (n+1)th pass; later passes report nothing."""

    def __init__(self, issues_per_pass):
        self.issues_per_pass, self.passes = issues_per_pass, 0

    def __call__(self, state, llm):
        issues = self.issues_per_pass[self.passes] if self.passes < len(self.issues_per_pass) else []
        self.passes += 1
        return replace(FAKE, issues=list(issues))


def run_with_renderer(issues_per_pass, qa=None):
    agents, counts = counted(replace(stub_agents(qa=qa), renderer=ScriptedRenderer(issues_per_pass)))
    run = Run(agents)
    run.start()
    return run, counts


def test_a_render_result_has_no_issues_unless_given():
    assert FAKE.issues == []
    assert stub_agents().renderer(sample_state().model_copy(update={"spec": _spec()}), FakeLLM({})).issues == []


def _spec():
    from tests.support import GOOD_COPY

    return stub_agents().layout(sample_state().model_copy(update={"slot_copy": GOOD_COPY}), FakeLLM({}))


def test_the_scripted_qa_passes_render_issues_through_with_its_own():
    scripted = qa_issue("layout", "scripted")
    state = sample_state().model_copy(update={"qa_issues": [overflow()]})
    assert ScriptedQA([[scripted]])(state, FakeLLM({})) == [overflow(), scripted]
    assert ScriptedQA()(state.model_copy(update={"qa_round": 1}), FakeLLM({})) == [overflow()]


def test_the_scripted_qa_does_not_pass_on_its_own_earlier_issues():
    state = sample_state().model_copy(update={"qa_issues": [qa_issue("copywriter", "last round")]})
    assert ScriptedQA()(state, FakeLLM({})) == []


def test_a_text_overflow_sends_the_run_back_to_the_copywriter():
    run, calls = run_with_renderer([[overflow()]])
    assert run.paused_at == ("human_review",)
    assert (calls["copywriter"], calls["layout"], calls["renderer"], calls["qa"]) == (2, 2, 2, 2)
    assert run.state.qa_round == 2
    assert run.state.spec.qa_warnings == []


def test_the_copywriter_sees_the_overflow_on_its_second_pass():
    seen = []
    agents = stub_agents()
    copywriter = agents.copywriter

    def watching(state, llm):
        seen.append([i.check for i in state.qa_issues if i.route_to == "copywriter"])
        return copywriter(state, llm)

    run = Run(replace(agents, copywriter=watching, renderer=ScriptedRenderer([[overflow()]])))
    run.start()
    assert seen == [[], ["render.text_overflow"]]


def test_an_overflow_left_after_3_rounds_ends_up_in_the_spec_warnings():
    run, calls = run_with_renderer([[overflow(f"pass {n}")] for n in range(1, 6)])
    assert run.paused_at == ("human_review",)
    assert (calls["copywriter"], calls["layout"], calls["renderer"], calls["qa"]) == (3, 3, 3, 3)
    assert run.state.qa_round == 3
    assert [(i.check, i.note) for i in run.state.spec.qa_warnings] == [("render.text_overflow", "pass 3")]


def test_render_issues_and_scripted_qa_issues_route_together():
    run, calls = run_with_renderer([[overflow()]], qa=ScriptedQA([[qa_issue("none", "cosmetic")]]))
    assert (calls["copywriter"], calls["qa"]) == (2, 2)
    assert run.state.spec.qa_warnings == []  # the run looped, so round 1's issues were not the last word


def test_with_no_render_issues_the_run_is_unchanged():
    run, calls = run_with_renderer([])
    assert run.paused_at == ("human_review",)
    assert (calls["copywriter"], calls["layout"], calls["renderer"], calls["qa"]) == (1, 1, 1, 1)
    assert run.state.qa_round == 1 and run.state.qa_issues == [] and run.state.spec.qa_warnings == []


def test_the_real_renderer_returns_the_issues_the_render_found(tmp_path):
    def render(spec, brand_kit, image_tags, image_dir, out_dir, *, brand_dir=None):
        out = Path(out_dir)
        return out / "brochure.pdf", [out / f"page-{n}.png" for n in range(1, 9)], [overflow()]

    state = sample_state().model_copy(update={"spec": _spec()})
    result = RealRenderer(tmp_path, REPO_ROOT / "sample", render=render)(state, FakeLLM({}))
    assert result.issues == [overflow()]


def verbatim_overflow(note="config_table: the text is 200 mm tall but the slot is 114 mm"):
    return QAIssue(check="render.text_overflow", page=5, severity="warning", note=note, route_to="none")


def test_a_verbatim_overflow_does_not_send_the_run_back_and_is_shown_to_the_reviewer():
    run, calls = run_with_renderer([[verbatim_overflow()]])
    assert run.paused_at == ("human_review",)
    assert (calls["copywriter"], calls["layout"], calls["renderer"], calls["qa"]) == (1, 1, 1, 1)
    assert run.state.spec.qa_warnings == [verbatim_overflow()]
