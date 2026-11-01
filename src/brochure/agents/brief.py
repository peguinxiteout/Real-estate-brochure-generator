"""The Brief agent: fills empty form fields with facts the user's prompt states, and nothing else."""
from pathlib import Path

from pydantic import BaseModel, ConfigDict

from brochure.contracts.project import Brief, BriefForm, Configuration, Landmark, Specification
from brochure.llm import LLMClient, TaskSpec

TASK = "brief.extract"
PROMPT_FILE = Path(__file__).parent / "prompts" / "brief_extract.md"


class _Reply(BaseModel):
    model_config = ConfigDict(extra="forbid")


class FoundConfiguration(_Reply):
    label: str
    carpet_area_sqft: float


class FoundSpecification(_Reply):
    category: str
    detail: str


class FoundLandmark(_Reply):
    name: str
    distance_km: float


class Extraction(_Reply):
    """What the model must return: the form's fields, each null (or []) when the prompt does not state it."""

    name: str | None = None
    rera_number: str | None = None
    rera_state: str | None = None
    location: str | None = None
    configurations: list[FoundConfiguration] = []
    amenities: list[str] = []
    specifications: list[FoundSpecification] = []
    landmarks: list[FoundLandmark] = []
    possession: str | None = None
    tone_notes: str | None = None


def _blank(value: str | None) -> bool:
    return not (value or "").strip()


def _merge(form: BriefForm, found: Extraction) -> BriefForm:
    """The form with each of its empty fields filled from `found`. A field that has a value is never touched."""
    fill = {}
    for field in ("name", "rera_number", "rera_state", "location", "possession", "tone_notes"):
        if _blank(getattr(form, field)) and not _blank(getattr(found, field)):
            fill[field] = getattr(found, field)
    items = {
        "configurations": [Configuration(**c.model_dump()) for c in found.configurations],
        "amenities": list(found.amenities),
        "specifications": [Specification(**s.model_dump()) for s in found.specifications],
        "landmarks": [Landmark(**m.model_dump()) for m in found.landmarks],
    }
    for field, values in items.items():
        if not getattr(form, field) and values:
            fill[field] = values
    return form.model_copy(update=fill)


def brief_agent(brief: Brief, llm: LLMClient) -> BriefForm:
    payload = {"form": brief.form.model_dump(), "prompt": brief.prompt}
    found = Extraction.model_validate(llm.complete(TASK, payload))
    return _merge(brief.form, found)
