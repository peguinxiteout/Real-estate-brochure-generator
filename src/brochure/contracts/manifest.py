"""images.json: the list of images in a project folder and which slot each is meant for."""
from typing import Literal

from brochure.contracts.base import ContractModel


class ImageManifestEntry(ContractModel):
    filename: str
    width_px: int
    height_px: int
    kind: Literal["photo", "render", "floor_plan", "map"]
    intended_slot: str


class ImageManifest(ContractModel):
    images: list[ImageManifestEntry]
