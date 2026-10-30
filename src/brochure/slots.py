"""Load slots.json and work out each slot's physical size and minimum pixels."""
from pathlib import Path

from brochure.contracts.base import ContractModel
from brochure.contracts.slots import Slot, SlotsFile
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


def load_slots(path: Path, config: PrintConfig = PRINT) -> SlotTemplate:
    file = SlotsFile.model_validate_json(Path(path).read_text(encoding="utf-8"))
    return SlotTemplate(template_id=file.template_id, slots=[ResolvedSlot(**s.model_dump()) for s in file.slots])
