"""The agents set with the real agents in place of their stubs. Everything not listed here is still a stub."""
from dataclasses import replace

from brochure.agents.brief import brief_agent
from brochure.contracts.project import ProjectFacts
from brochure.contracts.state import PipelineState
from brochure.llm import LLMClient
from brochure.pipeline.agents import Agents, BriefOutcome
from brochure.pipeline.brief import missing_fields
from brochure.pipeline.stubs import SampleData, stub_agents


def real_brief_step(state: PipelineState, llm: LLMClient) -> BriefOutcome:
    """The brief step on the Brief agent's merged form: facts if nothing is missing, else the fields to ask for."""
    form = brief_agent(state.brief, llm)
    missing = missing_fields(form)
    if missing:
        return BriefOutcome(project_facts=None, missing_fields=missing, form=form)
    return BriefOutcome(project_facts=ProjectFacts.model_validate(form.model_dump()), missing_fields=[], form=form)


def real_agents(llm: LLMClient, data: SampleData | None = None, qa=None) -> Agents:
    """Real Brief agent (bound to `llm`) and the stubs for every other step."""
    return replace(stub_agents(data, qa), brief=lambda state, _graph_llm: real_brief_step(state, llm))
