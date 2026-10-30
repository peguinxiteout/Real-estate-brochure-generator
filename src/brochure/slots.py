"""Load slots.json and work out each slot's physical size and minimum pixels."""
from fractions import Fraction
from pathlib import Path

from brochure.contracts.base import ContractModel
from brochure.contracts.slots import Slot, SlotsFile
from brochure.dpi import min_pixels
from brochure.print_config import PRINT, PrintConfig


class ResolvedSlot(Slot):
    """A slot from the file plus what the print config says about it. Never written back to the file."""

    bleed_width_mm: float = 0
    bleed_height_mm: float = 0
    min_px: tuple[int, int] | None = None


class SlotTemplate(ContractModel):
    template_id: str
    slots: list[ResolvedSlot]

    def get(self, slot_id: str) -> ResolvedSlot:
        return next(s for s in self.slots if s.id == slot_id)


def _resolve(slot: Slot, config: PrintConfig) -> ResolvedSlot:
    bleed = Fraction(str(config.bleed_mm))
    width = Fraction(str(slot.width_mm)) + bleed * sum(edge in slot.bleed_edges for edge in ("left", "right"))
    height = Fraction(str(slot.height_mm)) + bleed * sum(edge in slot.bleed_edges for edge in ("top", "bottom"))
    min_px = None
    if slot.type == "image":
        min_px = (min_pixels(width, config.target_dpi), min_pixels(height, config.target_dpi))
    return ResolvedSlot(**slot.model_dump(), bleed_width_mm=float(width), bleed_height_mm=float(height), min_px=min_px)


def load_slots(path: Path, config: PrintConfig = PRINT) -> SlotTemplate:
    file = SlotsFile.model_validate_json(Path(path).read_text(encoding="utf-8"))
    return SlotTemplate(template_id=file.template_id, slots=[_resolve(s, config) for s in file.slots])
