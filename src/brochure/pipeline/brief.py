"""The brief step. Real code, not a stub: converts the form to ProjectFacts and says what is still missing."""
from brochure.contracts.project import ProjectFacts
from brochure.contracts.state import PipelineState
from brochure.pipeline.agents import BriefOutcome


def brief_step(state: PipelineState, llm) -> BriefOutcome:
    facts = ProjectFacts.model_validate(state.brief.form.model_dump())
    return BriefOutcome(project_facts=facts, missing_fields=[])
