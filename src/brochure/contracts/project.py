"""Project facts: what the developer tells us about the project."""
from typing import Annotated

from pydantic import Field, StringConstraints

from brochure.contracts.base import ContractModel


class Configuration(ContractModel):
    label: str
    carpet_area_sqft: float = Field(gt=0)


class Specification(ContractModel):
    category: str
    detail: str


class Landmark(ContractModel):
    name: str
    distance_km: float


NonBlank = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]


class ProjectFacts(ContractModel):
    name: str
    rera_number: NonBlank
    rera_state: str
    location: str
    configurations: list[Configuration] = []
    amenities: list[str] = []
    specifications: list[Specification] = []
    landmarks: list[Landmark] = []
    possession: str
    tone_notes: str = ""


class BriefForm(ContractModel):
    """What the user filled in on the form: ProjectFacts with every field optional."""

    name: str | None = None
    rera_number: str | None = None
    rera_state: str | None = None
    location: str | None = None
    configurations: list[Configuration] = []
    amenities: list[str] = []
    specifications: list[Specification] = []
    landmarks: list[Landmark] = []
    possession: str | None = None
    tone_notes: str | None = None


class Brief(ContractModel):
    """The user's starting point: structured facts plus a free-text prompt."""

    project_facts: ProjectFacts
    prompt: str
