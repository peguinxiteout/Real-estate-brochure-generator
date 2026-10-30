"""The fixed pipeline graph. It knows the steps by name only; the agents come in through `Agents`."""
from typing import Literal

from langgraph.graph import END, START, StateGraph
from langgraph.types import Command, interrupt

from brochure.contracts.project import BriefForm
from brochure.contracts.state import PipelineState
from brochure.pipeline.agents import Agents


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
        return {"qa_issues": agents.qa(state, llm), "qa_round": state.qa_round + 1}

    def human_review(state: PipelineState) -> Command[Literal["export"]]:
        interrupt({"ask": "review", "pdf_path": state.pdf_path, "page_images": state.page_images})
        return Command(goto="export", update={"approval_status": "approved"})

    def export(state: PipelineState):
        agents.export(state, llm)
        return {}

    graph = StateGraph(PipelineState)
    for name, step in [
        ("brief", brief), ("ask_user", ask_user), ("vision", vision), ("brief_ready", brief_ready), ("copywriter", copywriter),
        ("layout", layout), ("renderer", renderer), ("qa", qa), ("export", export),
    ]:
        graph.add_node(name, step)
    graph.add_node("human_review", human_review, destinations=("export",))

    graph.add_edge(START, "brief")
    graph.add_edge(START, "vision")
    graph.add_conditional_edges("brief", after_brief)
    graph.add_edge("ask_user", "brief")
    graph.add_edge(["brief_ready", "vision"], "copywriter")
    graph.add_edge("copywriter", "layout")
    graph.add_edge("layout", "renderer")
    graph.add_edge("renderer", "qa")
    graph.add_edge("qa", "human_review")
    graph.add_edge("export", END)
    return graph.compile(checkpointer=checkpointer)
