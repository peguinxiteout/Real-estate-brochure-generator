"""slots.json: the fixed boxes a template offers, as written in the file."""
from typing import Literal

from pydantic import model_validator

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

    @model_validator(mode="after")
    def _char_budget_belongs_to_text_slots(self) -> "Slot":
        if self.type == "text" and self.char_budget is None:
            raise ValueError(f"text slot {self.id!r} needs a char_budget")
        if self.type != "text" and self.char_budget is not None:
            raise ValueError(f"only text slots have a char_budget, but {self.type} slot {self.id!r} has one")
        return self

    @model_validator(mode="after")
    def _bleed_edges_are_unique(self) -> "Slot":
        if len(set(self.bleed_edges)) != len(self.bleed_edges):
            raise ValueError(f"slot {self.id!r} lists a bleed edge more than once")
        return self
