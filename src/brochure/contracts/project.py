"""Project facts: what the developer tells us about the project."""
from pydantic import Field

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


class ProjectFacts(ContractModel):
    name: str
    rera_number: str
    rera_state: str
    location: str
    configurations: list[Configuration] = []
    amenities: list[str] = []
    specifications: list[Specification] = []
    landmarks: list[Landmark] = []
    possession: str
    tone_notes: str = ""
