"""slots.json: the fixed boxes a template offers, as written in the file."""
from typing import Literal

from brochure.contracts.base import ContractModel

Edge = Literal["top", "right", "bottom", "left"]


class Slot(ContractModel):
    id: str
    type: Literal["image", "text", "qr"]
    page: int
    width_mm: float
    height_mm: float
    bleed_edges: list[Edge] = []
    char_budget: int | None = None
    comment: str = ""
