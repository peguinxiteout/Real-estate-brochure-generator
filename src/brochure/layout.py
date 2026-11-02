"""Image assignment for the Layout step: which project image goes in which image slot. Rule-based, no LLM, deterministic.

The rules (accepted kinds, preferred subject keywords, the order in which slots pick) live in the template's
layout_rules.json. They belong to the layout, not to the shared contracts.
"""
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from brochure.contracts.images import ImageTag
from brochure.dpi import DpiStatus, classify_dpi, effective_dpi
from brochure.slots import ResolvedSlot, SlotTemplate

LOGO_SLOTS = ("cover_logo", "back_logo")  # filled from the brand kit, never from the project's images

Kind = Literal["photo", "render", "floor_plan", "map"]


class SlotRule(BaseModel):
    model_config = ConfigDict(extra="forbid")

    slot: str
    kinds: list[Kind] = Field(min_length=1)  # the image kinds this slot accepts
    keywords: list[str] = []  # preferred words in an image's subject or features, any case
    priority: int = Field(ge=1)  # slots pick in this order, 1 first


class LayoutRules(BaseModel):
    model_config = ConfigDict(extra="forbid")

    template_id: str
    rules: list[SlotRule]


def load_layout_rules(path: Path) -> LayoutRules:
    return LayoutRules.model_validate_json(Path(path).read_text(encoding="utf-8"))


def rule_problems(rules: LayoutRules, template: SlotTemplate) -> list[str]:
    """Why these rules do not fit the template; empty when every non-logo image slot has exactly one rule and every
    rule names one of them."""
    problems = []
    if rules.template_id != template.template_id:
        problems.append(f"the rules are for template {rules.template_id!r}, not {template.template_id!r}")
    placeable = {s.id for s in template.slots if s.type == "image" and s.id not in LOGO_SLOTS}
    named = [r.slot for r in rules.rules]
    for slot_id in sorted(placeable - set(named)):
        problems.append(f"image slot {slot_id!r} has no layout rule")
    for slot_id in dict.fromkeys(named):
        if slot_id not in placeable:
            problems.append(f"rule for {slot_id!r}, which is not a non-logo image slot of the template")
        elif named.count(slot_id) > 1:
            problems.append(f"image slot {slot_id!r} has {named.count(slot_id)} layout rules")
    priorities = [r.priority for r in rules.rules]
    for priority in sorted({p for p in priorities if priorities.count(p) > 1}):
        slots = ", ".join(r.slot for r in rules.rules if r.priority == priority)
        problems.append(f"priority {priority} is given to more than one slot ({slots})")
    return problems


def fit(tag: ImageTag, slot: ResolvedSlot) -> tuple[float, DpiStatus]:
    """The image's effective DPI in the slot (slot size with its bleed, as everywhere) and its band."""
    dpi = effective_dpi(tag.width_px, tag.height_px, slot.bleed_width_mm, slot.bleed_height_mm)
    return dpi, classify_dpi(dpi)


def eligible(tag: ImageTag, slot: ResolvedSlot, rule: SlotRule) -> bool:
    """The slot accepts the image's kind and the image is not below the DPI floor there."""
    return tag.kind in rule.kinds and fit(tag, slot)[1] != DpiStatus.FAIL
