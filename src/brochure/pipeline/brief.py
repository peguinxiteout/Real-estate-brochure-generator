"""The brief step. Real code, not a stub: converts the form to ProjectFacts and says what is still missing."""
from pydantic import ValidationError

from brochure.contracts.project import BriefForm, ProjectFacts
from brochure.contracts.state import PipelineState
from brochure.pipeline.agents import BriefOutcome


def brief_step(state: PipelineState, llm) -> BriefOutcome:
    """Facts if the form is complete. Otherwise the top-level fields that failed ProjectFacts, in form order.

    A field counts as missing when it is absent, None, blank, or invalid: in each case the user has to supply it.
    """
    try:
        facts = ProjectFacts.model_validate(state.brief.form.model_dump())
    except ValidationError as error:
        failed = {e["loc"][0] for e in error.errors()}
        return BriefOutcome(project_facts=None, missing_fields=[f for f in BriefForm.model_fields if f in failed])
    return BriefOutcome(project_facts=facts, missing_fields=[])
