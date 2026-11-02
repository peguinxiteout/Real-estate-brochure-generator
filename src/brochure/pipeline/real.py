"""The agents set with the real steps in place of their stubs. Everything not listed here is still a stub."""
from dataclasses import replace

from brochure.agents.brief import brief_agent
from brochure.agents.copywriter import CopyInputs, copywriter_agent, owned_slots
from brochure.contracts.project import ProjectFacts
from brochure.contracts.spec import BrochureSpec
from brochure.contracts.state import PipelineState
from brochure.layout import LayoutRules, assign_images, load_layout_rules
from brochure.llm import LLMClient
from brochure.pipeline.agents import Agents, BriefOutcome
from brochure.pipeline.brief import missing_fields
from brochure.pipeline.stubs import REPO_ROOT, SampleData, layout_spec, load_sample_data, stub_agents
from brochure.slots import SlotTemplate
from brochure.verbatim import verbatim_copy


def real_brief_step(state: PipelineState, llm: LLMClient) -> BriefOutcome:
    """The brief step on the Brief agent's merged form: facts if nothing is missing, else the fields to ask for."""
    form = brief_agent(state.brief, llm)
    missing = missing_fields(form)
    if missing:
        return BriefOutcome(project_facts=None, missing_fields=missing, form=form)
    return BriefOutcome(project_facts=ProjectFacts.model_validate(form.model_dump()), missing_fields=[], form=form)


def real_copywriter_step(state: PipelineState, llm: LLMClient, template: SlotTemplate) -> dict[str, str]:
    """The slot copy: the verbatim slots from code, plus what the Copywriter wrote. A slot it could not write is absent."""
    inputs = CopyInputs(
        facts=state.project_facts,
        company_name=state.brand_kit.company_name,
        image_tags=state.image_tags,
        slots=owned_slots(template),
        qa_issues=[issue for issue in state.qa_issues if issue.route_to == "copywriter"],
    )
    return {**verbatim_copy(state.project_facts, state.brand_kit), **copywriter_agent(inputs, llm)}


def real_layout_step(state: PipelineState, llm: LLMClient, template: SlotTemplate, rules: LayoutRules) -> BrochureSpec:
    """The spec with the images assigned by the layout rules (no LLM call). Its findings are the spec's qa_warnings."""
    assignment = assign_images(template, rules, state.image_tags)
    images = {slot_id: p.image for slot_id, p in assignment.placements.items()}
    return layout_spec(state, template, images, assignment.findings)


def real_agents(data: SampleData | None = None, qa=None, rules: LayoutRules | None = None) -> Agents:
    """Real Brief and Copywriter agents, the rule-based layout, and the stubs for every other step. Each real step
    uses the llm that `build_graph` hands it."""
    data = data or load_sample_data()
    rules = rules or load_layout_rules(REPO_ROOT / "templates" / data.template.template_id / "layout_rules.json")
    return replace(
        stub_agents(data, qa),
        brief=real_brief_step,
        copywriter=lambda state, llm: real_copywriter_step(state, llm, data.template),
        layout=lambda state, llm: real_layout_step(state, llm, data.template, rules),
    )
