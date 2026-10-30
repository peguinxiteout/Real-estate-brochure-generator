"""The fixed pipeline graph. It knows the steps by name only; the agents come in through `Agents`."""
from typing import Literal

from langgraph.graph import END, START, StateGraph
from langgraph.types import Command, interrupt

from brochure.contracts.project import BriefForm
from brochure.contracts.qa import QAIssue
from brochure.contracts.state import PipelineState
from brochure.pipeline.agents import Agents


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
        return {"project_facts": outcome.project_facts, "missing_fields": outcome.missing_fields}

    def vision(state: PipelineState):
        return {"image_tags": agents.vision(state, llm)}

    def after_brief(state: PipelineState) -> Literal["ask_user", "brief_ready"]:
        return "ask_user" if state.missing_fields else "brief_ready"

    def ask_user(state: PipelineState):
        """Pause and ask for the missing fields. The caller resumes with {field: value}; the brief step then runs again."""
        answers = interrupt({"ask": "brief", "missing_fields": state.missing_fields})
        form = BriefForm.model_validate({**state.brief.form.model_dump(), **answers})
        return {"brief": state.brief.model_copy(update={"form": form})}

    def brief_ready(state: PipelineState):
        """Joins the brief branch with the vision branch; it does no work."""
        return {}

    def copywriter(state: PipelineState):
        return {"slot_copy": agents.copywriter(state, llm)}

    def layout(state: PipelineState):
        return {"spec": agents.layout(state, llm)}

    def renderer(state: PipelineState):
        result = agents.renderer(state, llm)
        return {"pdf_path": result.pdf_path, "page_images": result.page_images}

    def qa(state: PipelineState):
        issues, qa_round = agents.qa(state, llm), state.qa_round + 1
        update = {"qa_issues": issues, "qa_round": qa_round}
        if issues and qa_next(issues, qa_round) == "human_review":
            update["spec"] = state.spec.model_copy(update={"qa_warnings": issues})  # shown to the reviewer
        return update

    def after_qa(state: PipelineState) -> Literal["copywriter", "layout", "human_review"]:
        return qa_next(state.qa_issues, state.qa_round)

    def human_review(state: PipelineState) -> Command[Literal["export", "layout"]]:
        """Pause for a person. Resume with "approved" or "changes_requested"."""
        decision = interrupt({"ask": "review", "pdf_path": state.pdf_path, "page_images": state.page_images})
        if decision == "approved":
            return Command(goto="export", update={"approval_status": "approved"})
        if decision == "changes_requested":
            return Command(goto="layout", update={"approval_status": "pending", "qa_round": 0})
        raise ValueError(f"resume human_review with 'approved' or 'changes_requested', not {decision!r}")

    def export(state: PipelineState):
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
