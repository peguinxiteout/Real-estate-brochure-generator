"""The agents set with the real steps in place of their stubs. Everything not listed here is still a stub."""
import uuid
from dataclasses import replace
from datetime import datetime
from pathlib import Path

from brochure.agents.brief import brief_agent
from brochure.agents.copywriter import CopyInputs, copywriter_agent, owned_slots
from brochure.contracts.project import ProjectFacts
from brochure.contracts.spec import BrochureSpec
from brochure.contracts.state import PipelineState
from brochure.layout import LayoutRules, assign_images, load_layout_rules
from brochure.llm import LLMClient
from brochure.pipeline.agents import Agents, BriefOutcome, RenderResult
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


class RealRenderer:
    """The renderer step: the spec to a print PDF and page PNGs with WeasyPrint and Ghostscript, written into
    out_root/<thread id>/ (out_root/run-<time>-<id>/ when called outside a graph run). A relative logo_path is looked
    up in brand_dir. `render` is render_brochure; tests pass a fake."""

    def __init__(self, out_root: Path, brand_dir: Path, render=None):
        self.out_root, self.brand_dir = Path(out_root), Path(brand_dir)
        self.render = render

    def out_dir(self) -> Path:
        from langgraph.config import get_config

        try:
            thread_id = get_config().get("configurable", {}).get("thread_id")
        except RuntimeError:  # not inside a graph run
            thread_id = None
        name = str(thread_id) if thread_id else f"run-{datetime.now():%Y%m%d-%H%M%S}-{uuid.uuid4().hex[:6]}"
        return self.out_root / name

    def __call__(self, state: PipelineState, llm: LLMClient) -> RenderResult:
        render = self.render
        if render is None:
            from brochure.render.pdf import render_brochure as render
        pdf, pages = render(state.spec, state.brand_kit, state.image_tags, Path(state.image_dir), self.out_dir(),
                            brand_dir=self.brand_dir)
        return RenderResult(pdf_path=str(pdf), page_images=[str(p) for p in pages])


def real_agents(data: SampleData | None = None, qa=None, rules: LayoutRules | None = None, renderer=None,
                out_root: Path | None = None) -> Agents:
    """Real Brief and Copywriter agents, the rule-based layout, the real renderer, and the stubs for every other step.
    Each real step uses the llm that `build_graph` hands it.

    The renderer writes into out_root/<thread id>/ (default out/ in the repo); `renderer` replaces it (tests pass the
    stub, which needs no Pango)."""
    data = data or load_sample_data()
    renderer = renderer or RealRenderer(out_root or REPO_ROOT / "out", REPO_ROOT / "sample")
    rules = rules or load_layout_rules(REPO_ROOT / "templates" / data.template.template_id / "layout_rules.json")
    return replace(
        stub_agents(data, qa),
        brief=real_brief_step,
        copywriter=lambda state, llm: real_copywriter_step(state, llm, data.template),
        layout=lambda state, llm: real_layout_step(state, llm, data.template, rules),
        renderer=renderer,
    )
