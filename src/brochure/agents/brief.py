"""The Brief agent: fills empty form fields with facts the user's prompt states, and nothing else."""
import logging
import re
from pathlib import Path

from pydantic import BaseModel, ConfigDict

from brochure.contracts.project import Brief, BriefForm, Configuration, Landmark, Specification
from brochure.llm import LLMClient, TaskSpec

logger = logging.getLogger(__name__)

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


def _squash(text: str) -> str:
    return " ".join(text.split()).casefold()


def _numbers_in(text: str) -> set[float]:
    """Every number written in the text; a thousands comma ("1,090") is not part of the value."""
    return {float(n.replace(",", "")) for n in re.findall(r"\d[\d,]*(?:\.\d+)?", text)}


class _Grounding:
    """What the prompt actually says: a model value is kept only if it can be found here."""

    def __init__(self, prompt: str):
        self.prompt, self.text, self.numbers = prompt, _squash(prompt), _numbers_in(prompt)

    def string(self, value: str | None) -> str | None:
        """The value if the prompt contains it (any case, any spacing), else None."""
        return value if not _blank(value) and _squash(value) in self.text else None

    def rera(self, value: str | None) -> str | None:
        """A RERA number is a legal fact: it must appear in the prompt exactly as the model gives it."""
        return value if not _blank(value) and value.strip() in self.prompt else None

    def number(self, value: float) -> bool:
        return value in self.numbers

    def grounded(self, found: Extraction) -> Extraction:
        """`found` without every value the prompt does not support."""
        scalars = {f: self.string(getattr(found, f)) for f in ("name", "rera_state", "location", "possession", "tone_notes")}
        return Extraction(
            **scalars,
            rera_number=self.rera(found.rera_number),
            configurations=[c for c in found.configurations if self.string(c.label) and self.number(c.carpet_area_sqft)],
            amenities=[a for a in found.amenities if self.string(a)],
            specifications=[x for x in found.specifications if self.string(x.category) and self.string(x.detail)],
            landmarks=[m for m in found.landmarks if self.string(m.name) and self.number(m.distance_km)],
        )


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
    return _merge(brief.form, _Grounding(brief.prompt).grounded(found))
