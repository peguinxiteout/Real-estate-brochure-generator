"""Image tags: what the vision step (or a fixture) says about one image."""
from typing import Literal

from pydantic import Field

from brochure.contracts.base import ContractModel


class FocalPoint(ContractModel):
    """Where the subject sits in the image, as fractions of width (x) and height (y)."""

    x: float = Field(ge=0, le=1)
    y: float = Field(ge=0, le=1)


class ImageTag(ContractModel):
    path: str
    kind: Literal["photo", "render", "floor_plan", "map"]
    subject: str
    width_px: int = Field(gt=0)
    height_px: int = Field(gt=0)
    quality: Literal["good", "fair", "poor"]
    features: list[str] = []
    focal_point: FocalPoint
