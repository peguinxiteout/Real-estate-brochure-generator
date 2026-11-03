"""The fixed pipeline graph. It knows the steps by name only; the agents come in through `Agents`."""
from typing import Literal

from langgraph.graph import END, START, StateGraph
from langgraph.types import Command, interrupt

from brochure.contracts.qa import QAIssue
from brochure.contracts.state import PipelineState
from brochure.legal import blocking_for, is_lost_text
from brochure.pipeline.agents import Agents
from brochure.pipeline.brief import apply_answers, missing_fields


MAX_QA_ROUNDS = 3


def qa_next(issues: list[QAIssue], qa_round: int) -> Literal["copywriter", "layout", "human_review"]:
    """Where the run goes after a QA pass: the earliest step an issue is routed to, otherwise on to review.

    After MAX_QA_ROUNDS passes the run moves on to review whatever the issues say.
    """
    if qa_round >= MAX_QA_ROUNDS:
        return "human_review"
    routes = {issue.route_to for issue in issues}
    if "copywriter" in routes:
        return "copywriter"
    if "layout" in routes:
        return "layout"
    return "human_review"


def build_graph(agents: Agents, checkpointer, llm):
    """Compile the pipeline over PipelineState. `agents` and `llm` are supplied by the caller."""

    def brief(state: PipelineState):
        outcome = agents.brief(state, llm)
        update = {"project_facts": outcome.project_facts, "missing_fields": outcome.missing_fields}
        if outcome.form is not None:  # the step filled in fields; ask_user must work on that form, not the original
            update["brief"] = state.brief.model_copy(update={"form": outcome.form})
        return update

    def vision(state: PipelineState):
        return {"image_tags": agents.vision(state, llm)}

    def after_brief(state: PipelineState) -> Literal["ask_user", "brief_ready"]:
        return "ask_user" if state.missing_fields else "brief_ready"

    def ask_user(state: PipelineState):
        """Pause until the missing fields are supplied. The caller resumes with {field: value}.

        Answers that are refused are not applied; the question is asked again with the fields still missing
        and a short message for each refused field. The brief step runs again once nothing is missing.
        """
        form, missing, errors = state.brief.form, state.missing_fields, {}
        while True:
            answers = interrupt({"ask": "brief", "missing_fields": missing, "errors": errors})
            form, errors = apply_answers(form, answers)
            missing = missing_fields(form)
            if not missing and not errors:
                return {"brief": state.brief.model_copy(update={"form": form})}

    def brief_ready(state: PipelineState):
        """Joins the brief branch with the vision branch; it does no work."""
        return {}

    def copywriter(state: PipelineState):
        return {"slot_copy": agents.copywriter(state, llm)}

    def layout(state: PipelineState):
        return {"spec": agents.layout(state, llm)}

    def renderer(state: PipelineState):
        """The render's own findings (text overflow) go in qa_issues for the QA step, which returns them with its own;
        nothing reads qa_issues between here and QA."""
        result = agents.renderer(state, llm)
        return {"pdf_path": result.pdf_path, "page_images": result.page_images, "qa_issues": list(result.issues)}

    def qa(state: PipelineState):
        issues, qa_round = agents.qa(state, llm), state.qa_round + 1
        # lost text is what blocks approval, so a QA step that forgets to pass it on must not be able to unblock it
        issues = [*[i for i in state.qa_issues if is_lost_text(i) and i not in issues], *issues]
        update = {"qa_issues": issues, "qa_round": qa_round}
        if issues and qa_next(issues, qa_round) == "human_review":
            # shown to the reviewer, after the layout's own findings (the layout rebuilds the spec on every pass)
            update["spec"] = state.spec.model_copy(update={"qa_warnings": [*state.spec.qa_warnings, *issues]})
        return update

    def after_qa(state: PipelineState) -> Literal["copywriter", "layout", "human_review"]:
        return qa_next(state.qa_issues, state.qa_round)

    def human_review(state: PipelineState) -> Command[Literal["export", "layout"]]:
        """Pause for a person. Resume with "approved" or "changes_requested". "approved" is refused, and the question
        asked again, while legal content is missing from the print file."""
        blocking = blocking_for(state.spec)
        question = {
            "ask": "review", "pdf_path": state.pdf_path, "page_images": state.page_images, "error": None,
            "blocking": [{"check": i.check, "page": i.page, "note": i.note} for i in blocking],
        }
        decision = interrupt(question)
        while decision != "changes_requested":
            if decision == "approved":
                if not blocking:
                    return Command(goto="export", update={"approval_status": "approved"})
                error = f"can't approve: {blocking[0].note}"
            else:
                error = f"answer 'approved' or 'changes_requested', not {decision!r}"
            decision = interrupt({**question, "error": error})
        return Command(goto="layout", update={"approval_status": "pending", "qa_round": 0})

    def export(state: PipelineState):
        if blocking := blocking_for(state.spec):
            raise RuntimeError(f"can't export: {blocking[0].note}")
        agents.export(state, llm)
        return {}

    graph = StateGraph(PipelineState)
    for name, step in [
        ("brief", brief), ("ask_user", ask_user), ("vision", vision), ("brief_ready", brief_ready), ("copywriter", copywriter),
        ("layout", layout), ("renderer", renderer), ("qa", qa), ("export", export),
    ]:
        graph.add_node(name, step)
    graph.add_node("human_review", human_review, destinations=("export", "layout"))

    graph.add_edge(START, "brief")
    graph.add_edge(START, "vision")
    graph.add_conditional_edges("brief", after_brief)
    graph.add_edge("ask_user", "brief")
    graph.add_edge(["brief_ready", "vision"], "copywriter")
    graph.add_edge("copywriter", "layout")
    graph.add_edge("layout", "renderer")
    graph.add_edge("renderer", "qa")
    graph.add_conditional_edges("qa", after_qa)
    graph.add_edge("export", END)
    return graph.compile(checkpointer=checkpointer)
