"""The brief step. Real code, not a stub: converts the form to ProjectFacts and says what is still missing."""
from pydantic import ValidationError

from brochure.contracts.project import BriefForm, ProjectFacts
from brochure.contracts.state import PipelineState
from brochure.pipeline.agents import BriefOutcome


def _readable(error: dict) -> str:
    """One short sentence for a pydantic error, without the field name (the caller keys it by field)."""
    where = ".".join(str(part) for part in error["loc"][1:])
    if error["type"] == "missing" or (error["type"] == "string_type" and error["input"] is None):
        what = "required"
    elif error["type"] == "string_too_short":
        what = "must not be empty"
    else:
        what = error["msg"]
    return f"{where}: {what}" if where else what


def field_problems(form: BriefForm) -> dict[str, str]:
    """Why each top-level field stops the form becoming ProjectFacts, in form order. Empty when it converts."""
    try:
        ProjectFacts.model_validate(form.model_dump())
    except ValidationError as error:
        first = {}
        for e in error.errors():
            first.setdefault(e["loc"][0], _readable(e))
        return {f: first[f] for f in BriefForm.model_fields if f in first}
    return {}


def missing_fields(form: BriefForm) -> list[str]:
    """The fields the user still has to supply: absent, None, blank or invalid, in form order."""
    return list(field_problems(form))


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
        try:
            candidate = BriefForm.model_validate({**form.model_dump(), field: value})
        except ValidationError as error:
            errors[field] = _readable(error.errors()[0])
            continue
        problem = field_problems(candidate).get(field)
        if problem:
            errors[field] = problem
            continue
        form = candidate
    return form, errors
