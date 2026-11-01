"""The brief step. Real code, not a stub: converts the form to ProjectFacts and says what is still missing."""
from pydantic import ValidationError

from brochure.contracts.project import BriefForm, ProjectFacts
from brochure.contracts.state import PipelineState
from brochure.pipeline.agents import BriefOutcome


def missing_fields(form: BriefForm) -> list[str]:
    """The top-level fields that stop the form becoming ProjectFacts, in form order.

    A field counts as missing when it is absent, None, blank, or invalid: in each case the user has to supply it.
    """
    try:
        ProjectFacts.model_validate(form.model_dump())
    except ValidationError as error:
        failed = {e["loc"][0] for e in error.errors()}
        return [f for f in BriefForm.model_fields if f in failed]
    return []


def brief_step(state: PipelineState, llm) -> BriefOutcome:
    form = state.brief.form
    missing = missing_fields(form)
    if missing:
        return BriefOutcome(project_facts=None, missing_fields=missing)
    return BriefOutcome(project_facts=ProjectFacts.model_validate(form.model_dump()), missing_fields=[])


def apply_answers(form: BriefForm, answers: dict) -> tuple[BriefForm, dict[str, str]]:
    """Put each answered field into the form. Returns the new form and a short message for every field refused."""
    errors: dict[str, str] = {}
    for field, value in answers.items():
        if field not in BriefForm.model_fields:
            errors[field] = "unknown field"
            continue
        form = BriefForm.model_validate({**form.model_dump(), field: value})
    return form, errors
