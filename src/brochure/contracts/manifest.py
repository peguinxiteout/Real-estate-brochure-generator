"""images.json: the list of images in a project folder and which slot each is meant for."""
from typing import Literal

from pydantic import Field

from brochure.contracts.base import ContractModel


class ImageManifestEntry(ContractModel):
    filename: str
    width_px: int = Field(gt=0)
    height_px: int = Field(gt=0)
    kind: Literal["photo", "render", "floor_plan", "map"]
    intended_slot: str


class ImageManifest(ContractModel):
    images: list[ImageManifestEntry]
