"""Project facts: what the developer tells us about the project."""
from typing import Annotated

from pydantic import StringConstraints

from brochure.contracts.base import ContractModel


class Configuration(ContractModel):
    label: str
    carpet_area_sqft: float


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
