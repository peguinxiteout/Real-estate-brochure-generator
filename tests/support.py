"""Shared helpers for the pipeline tests: the sample project as a PipelineState."""
import json
from pathlib import Path

from brochure.contracts.brand import BrandKit
from brochure.contracts.project import Brief, ProjectFacts
from brochure.contracts.state import PipelineState

ROOT = Path(__file__).parents[1]


def sample_state(*, briefed: bool = True, brief_file: str = "brief.json", **form_changes) -> PipelineState:
    """The Aurelia Heights sample as a PipelineState.

    briefed=True sets project_facts, as it is after the brief step. brief_file picks the brief in sample/.
    form_changes override fields of the brief form.
    """
    brand = BrandKit.model_validate(json.loads((ROOT / "sample" / "brand_kit.json").read_text(encoding="utf-8")))
    brief = Brief.model_validate(json.loads((ROOT / "sample" / brief_file).read_text(encoding="utf-8")))
    brief = brief.model_copy(update={"form": brief.form.model_copy(update=form_changes)})
    facts = ProjectFacts.model_validate(brief.form.model_dump()) if briefed else None
    return PipelineState(
        template_id="classic-8pp", brand_kit=brand, brief=brief, image_dir="sample/images", project_facts=facts
    )


class Run:
    """One pipeline run: a graph, its thread config, and a FakeLLM (empty unless `llm` is given)."""

    created: list["Run"] = []  # every Run made, so a test fixture can check them all

    def __init__(self, agents=None, checkpointer=None, thread_id="run-1", llm=None):
        from brochure.llm import FakeLLM
        from brochure.pipeline import build_graph, memory_checkpointer, stub_agents

        self.llm = llm or FakeLLM({})
        self.graph = build_graph(agents or stub_agents(), checkpointer or memory_checkpointer(), self.llm)
        self.config = {"configurable": {"thread_id": thread_id}}
        Run.created.append(self)

    def start(self, state=None):
        return self.graph.invoke(state or sample_state(briefed=False), self.config)

    def resume(self, value):
        from langgraph.types import Command

        return self.graph.invoke(Command(resume=value), self.config)

    @property
    def paused_at(self) -> tuple[str, ...]:
        return self.graph.get_state(self.config).next

    @property
    def interrupt_value(self):
        """What the run is asking for right now."""
        return self.graph.get_state(self.config).tasks[0].interrupts[0].value

    @property
    def state(self) -> PipelineState:
        return PipelineState.model_validate(self.graph.get_state(self.config).values)


def counted(agents):
    """The same agents, each wrapped to count its calls. Returns (agents, counts) where counts maps step name -> calls."""
    from dataclasses import fields, replace

    counts = {f.name: 0 for f in fields(agents)}

    def wrap(name, agent):
        def counting(state, llm):
            counts[name] += 1
            return agent(state, llm)

        return counting

    return replace(agents, **{name: wrap(name, getattr(agents, name)) for name in counts}), counts


def qa_issue(route_to, note="problem"):
    from brochure.contracts.qa import QAIssue

    return QAIssue(check="stub", page=1, severity="error", note=note, route_to=route_to)
