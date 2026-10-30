"""The pipeline graph on stub agents: the whole flow runs with no LLM and no rendering."""
from dataclasses import replace

from brochure.pipeline import stub_agents
from tests.support import Run


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
