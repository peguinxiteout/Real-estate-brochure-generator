"""Where each slot of a template sits on its page (templates/<id>/positions.json). Owned by the template, not a shared
contract: the sizes stay in slots.json and are never repeated here.

Coordinates are in mm from the top-left corner of the trim, y downwards (as in CSS). A position is the top-left corner
of the slot's trim-side box: its slots.json size, without bleed. The renderer draws the slot grown by the bleed on each
of its bleed_edges (see drawn_rect), which is the size slots.py measures it at.

The rules (position_problems):
- every slot has exactly one position and every position names a slot of the template;
- a text slot has one of ROLES, any other slot has none;
- on each edge in bleed_edges the trim-side box lies exactly on the trim edge, so the drawn box ends exactly bleed_mm
  past the trim there; on every other edge it lies strictly inside the trim (it never touches the trim edge);
- text and QR slots lie inside the safe area: the trim inset by safe_margin_mm on every edge;
- no two slots on a page overlap, except the pairs listed in overlays: a text, QR or logo slot on a non-logo image slot.
  A listed pair must overlap;
- any non-logo image may be a render, so each has a caption box (caption_rect, in the corner its position names): the
  box lies inside the image and outside every slot listed over the image and every decoration on the page;
- static text (words that belong to the template, not slots) has a role, lies inside the safe area and overlaps no slot
  and no other static text.

Separately, gap_problems: the white space between consecutive blocks on a page stays within max_block_gap_mm, except
above the blocks named in free_gap_above. It is a design rule of a finished template, so it is not part of the checks
above, which run on every render.
"""
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict

from brochure.layout import LOGO_SLOTS
from brochure.print_config import PRINT, PrintConfig
from brochure.slots import ResolvedSlot, SlotTemplate

ROLES = ("title", "heading", "subheading", "body", "list", "small-print")
EPS = 1e-9
CAPTION_WIDTH_MM = 27  # holds "Artist's impression" at the caption's size; the renderer draws the box at exactly this size
CAPTION_HEIGHT_MM = 4.5
CAPTION_INSET_MM = 2.5  # from a slot edge that does not bleed


class SlotPosition(BaseModel):
    model_config = ConfigDict(extra="forbid")

    slot: str
    x_mm: float
    y_mm: float
    role: str | None = None  # text slots only: which text style the template gives it
    caption: Literal["top-right", "bottom-right"] = "bottom-right"  # image slots: the corner for a render's caption


class Overlay(BaseModel):
    """`slot` is drawn on top of `over`, by design."""

    model_config = ConfigDict(extra="forbid")

    slot: str
    over: str


class Decoration(BaseModel):
    """A band of colour drawn behind the slots on the listed pages. `id` is its CSS class; the box may bleed."""

    model_config = ConfigDict(extra="forbid")

    id: str
    pages: list[int]
    x_mm: float
    y_mm: float
    width_mm: float
    height_mm: float


class StaticText(BaseModel):
    """Words that belong to the template, such as a section title: not a slot, so nobody writes or fills them."""

    model_config = ConfigDict(extra="forbid")

    id: str
    page: int
    x_mm: float
    y_mm: float
    width_mm: float
    height_mm: float
    role: str
    text: str


class PositionsFile(BaseModel):
    model_config = ConfigDict(extra="forbid")

    template_id: str
    positions: list[SlotPosition]
    overlays: list[Overlay] = []
    decorations: list[Decoration] = []
    static_text: list[StaticText] = []
    free_gap_above: list[str] = []  # blocks that may have any amount of white space above them

    def of(self, slot_id: str) -> SlotPosition:
        return next(p for p in self.positions if p.slot == slot_id)


@dataclass(frozen=True)
class Rect:
    """A box in mm from the trim's top-left corner, y downwards."""

    x: float
    y: float
    w: float
    h: float

    @property
    def left(self) -> float:
        return self.x

    @property
    def top(self) -> float:
        return self.y

    @property
    def right(self) -> float:
        return self.x + self.w

    @property
    def bottom(self) -> float:
        return self.y + self.h

    def overlaps(self, other: "Rect") -> bool:
        """True when the two share some area; boxes that only touch do not overlap."""
        return (min(self.right, other.right) - max(self.left, other.left) > EPS
                and min(self.bottom, other.bottom) - max(self.top, other.top) > EPS)


def load_positions(path: Path) -> PositionsFile:
    return PositionsFile.model_validate_json(Path(path).read_text(encoding="utf-8"))


def trim_rect(slot: ResolvedSlot, pos: SlotPosition) -> Rect:
    return Rect(pos.x_mm, pos.y_mm, slot.width_mm, slot.height_mm)


def drawn_rect(slot: ResolvedSlot, pos: SlotPosition, config: PrintConfig = PRINT) -> Rect:
    """The box the renderer draws: the trim-side box grown by the bleed on each of the slot's bleed edges."""
    edges = set(slot.bleed_edges)
    b = config.bleed_mm
    left = pos.x_mm - (b if "left" in edges else 0)
    top = pos.y_mm - (b if "top" in edges else 0)
    return Rect(left, top, slot.bleed_width_mm, slot.bleed_height_mm)


def caption_rect(slot: ResolvedSlot, pos: SlotPosition, config: PrintConfig = PRINT) -> Rect:
    """Where a render's caption goes: in the position's corner, inset CAPTION_INSET_MM from an edge of the slot, or on an
    edge that bleeds the safe margin inside the trim."""
    def inset(edge: str) -> float:
        return config.bleed_mm + config.safe_margin_mm if edge in slot.bleed_edges else CAPTION_INSET_MM

    drawn = drawn_rect(slot, pos, config)
    x = drawn.right - inset("right") - CAPTION_WIDTH_MM
    y = drawn.top + inset("top") if pos.caption == "top-right" else drawn.bottom - inset("bottom") - CAPTION_HEIGHT_MM
    return Rect(x, y, CAPTION_WIDTH_MM, CAPTION_HEIGHT_MM)


def static_rect(item: StaticText) -> Rect:
    return Rect(item.x_mm, item.y_mm, item.width_mm, item.height_mm)


def _num(v: float) -> str:
    return f"{v:g}"


def _edge_problems(slot: ResolvedSlot, r: Rect, config: PrintConfig) -> list[str]:
    W, H = config.page_width_mm, config.page_height_mm
    # edge -> (the box's coordinate on it, the trim edge, how it reads, which side is inside the trim)
    edges = {
        "left": (r.left, 0.0, "x = {} mm", +1, "x = 0"),
        "top": (r.top, 0.0, "y = {} mm", +1, "y = 0"),
        "right": (r.right, W, "right = {} mm", -1, f"{_num(W)} mm"),
        "bottom": (r.bottom, H, "bottom = {} mm", -1, f"{_num(H)} mm"),
    }
    found = []
    for edge, (value, trim, shown, inward, on_trim) in edges.items():
        if edge in slot.bleed_edges:
            if abs(value - trim) > EPS:
                found.append(f"{slot.id!r} bleeds off the {edge} edge, so its {edge} edge must be on the trim "
                             f"({on_trim}), not {_num(value)} mm")
        elif (value - trim) * inward <= EPS:
            found.append(f"{slot.id!r} does not bleed off the {edge} edge, so it must lie inside the trim there "
                         f"({shown.format(_num(value))})")
    return found


def _in_safe_area(r: Rect, config: PrintConfig) -> bool:
    m = config.safe_margin_mm
    return (r.left >= m - EPS and r.top >= m - EPS
            and r.right <= config.page_width_mm - m + EPS and r.bottom <= config.page_height_mm - m + EPS)


def position_problems(positions: PositionsFile, template: SlotTemplate, config: PrintConfig = PRINT) -> list[str]:
    """Why these positions break the rules in the module docstring; empty when they keep them all."""
    problems = []
    if positions.template_id != template.template_id:
        problems.append(f"the positions are for template {positions.template_id!r}, not {template.template_id!r}")
    slots = {s.id: s for s in template.slots}
    named = [p.slot for p in positions.positions]
    for slot_id in slots:
        if slot_id not in named:
            problems.append(f"slot {slot_id!r} has no position")
    for slot_id in dict.fromkeys(named):
        if slot_id not in slots:
            problems.append(f"position for {slot_id!r}, which is not a slot of the template")
        elif named.count(slot_id) > 1:
            problems.append(f"slot {slot_id!r} has {named.count(slot_id)} positions")

    placed: dict[str, Rect] = {}
    for pos in positions.positions:
        slot = slots.get(pos.slot)
        if slot is None or pos.slot in placed:
            continue
        r = placed[pos.slot] = trim_rect(slot, pos)
        if slot.type == "text" and pos.role not in ROLES:
            problems.append(f"text slot {slot.id!r} needs a role, one of {', '.join(ROLES)}; it has {pos.role!r}")
        if slot.type != "text" and pos.role is not None:
            problems.append(f"{slot.type} slot {slot.id!r} must not have a role")
        problems += _edge_problems(slot, r, config)
        if slot.type in ("text", "qr") and not _in_safe_area(r, config):
            problems.append(f"{slot.type} slot {slot.id!r} is outside the safe area ({_num(config.safe_margin_mm)} mm "
                            f"inside the trim): x {_num(r.left)} to {_num(r.right)}, y {_num(r.top)} to {_num(r.bottom)}")

    listed = set()
    for o in positions.overlays:
        if o.slot not in placed or o.over not in placed:
            problems.append(f"overlay {o.slot!r} over {o.over!r}: both must be positioned slots")
            continue
        upper, lower = slots[o.slot], slots[o.over]
        if lower.type != "image" or lower.id in LOGO_SLOTS or not (upper.type in ("text", "qr") or upper.id in LOGO_SLOTS):
            problems.append(f"overlay {o.slot!r} over {o.over!r}: only a text, QR or logo slot may lie on an image slot")
            continue
        if upper.page != lower.page or not placed[o.slot].overlaps(placed[o.over]):
            problems.append(f"overlay {o.slot!r} over {o.over!r}: they do not overlap, so the entry is not needed")
            continue
        listed.add(frozenset((o.slot, o.over)))

    ids = list(placed)
    for i, a in enumerate(ids):
        for b in ids[i + 1:]:
            if slots[a].page == slots[b].page and placed[a].overlaps(placed[b]) and frozenset((a, b)) not in listed:
                problems.append(f"{a!r} and {b!r} overlap on page {slots[a].page} and are not listed in overlays")
    return problems + _caption_problems(positions, slots, placed, config) + _static_problems(positions, slots, placed, config)


def _caption_problems(positions: PositionsFile, slots: dict[str, ResolvedSlot], placed: dict[str, Rect],
                      config: PrintConfig) -> list[str]:
    problems = []
    for slot_id in placed:
        slot = slots[slot_id]
        if slot.type != "image" or slot_id in LOGO_SLOTS:
            continue
        pos = positions.of(slot_id)
        box, drawn = caption_rect(slot, pos, config), drawn_rect(slot, pos, config)
        if (box.left < drawn.left - EPS or box.top < drawn.top - EPS
                or box.right > drawn.right + EPS or box.bottom > drawn.bottom + EPS):
            problems.append(f"the caption of {slot_id!r} does not fit inside the image")
            continue
        for o in positions.overlays:
            if o.over == slot_id and o.slot in placed and box.overlaps(placed[o.slot]):
                problems.append(f"the caption of {slot_id!r} lies under {o.slot!r}, which is listed over it; "
                                f"give {slot_id!r} another caption corner")
        for d in positions.decorations:
            if slot.page in d.pages and box.overlaps(Rect(d.x_mm, d.y_mm, d.width_mm, d.height_mm)):
                problems.append(f"the caption of {slot_id!r} lies under the decoration {d.id!r}; "
                                f"give {slot_id!r} another caption corner")
    return problems


def _static_problems(positions: PositionsFile, slots: dict[str, ResolvedSlot], placed: dict[str, Rect],
                     config: PrintConfig) -> list[str]:
    problems = []
    for n, item in enumerate(positions.static_text):
        r = static_rect(item)
        if item.role not in ROLES:
            problems.append(f"static text {item.id!r} needs a role, one of {', '.join(ROLES)}; it has {item.role!r}")
        if not _in_safe_area(r, config):
            problems.append(f"static text {item.id!r} is outside the safe area ({_num(config.safe_margin_mm)} mm inside the "
                            f"trim): x {_num(r.left)} to {_num(r.right)}, y {_num(r.top)} to {_num(r.bottom)}")
        for slot_id, other in placed.items():
            if slots[slot_id].page == item.page and r.overlaps(other):
                problems.append(f"static text {item.id!r} overlaps {slot_id!r} on page {item.page}")
        for earlier in positions.static_text[:n]:
            if earlier.page == item.page and r.overlaps(static_rect(earlier)):
                problems.append(f"static text {item.id!r} overlaps {earlier.id!r} on page {item.page}")
    return problems


@dataclass(frozen=True)
class BlockGap:
    page: int
    above: str
    below: str
    gap_mm: float


def block_gaps(positions: PositionsFile, template: SlotTemplate, text_heights: dict[str, float] | None = None) -> list[BlockGap]:
    """The white space between consecutive blocks on each page, top to bottom. A block is a slot or a piece of static
    text; a slot listed over another is part of that one. text_heights (slot id -> measured mm) replaces a text slot's
    box height with the height of its text."""
    heights = text_heights or {}
    over = {o.slot for o in positions.overlays}
    by_page: dict[int, list[tuple[float, float, str]]] = {}
    for pos in positions.positions:
        slot = template.get(pos.slot)
        if pos.slot not in over:
            top = pos.y_mm
            by_page.setdefault(slot.page, []).append((top, top + heights.get(pos.slot, slot.height_mm), pos.slot))
    for item in positions.static_text:
        by_page.setdefault(item.page, []).append((item.y_mm, item.y_mm + item.height_mm, item.id))
    gaps = []
    for page, blocks in sorted(by_page.items()):
        lowest, lowest_name = None, None
        for top, bottom, name in sorted(blocks):
            if lowest is not None and top - lowest > EPS:
                gaps.append(BlockGap(page, lowest_name, name, top - lowest))
            if lowest is None or bottom > lowest:
                lowest, lowest_name = bottom, name
    return gaps


def gap_problems(positions: PositionsFile, template: SlotTemplate, config: PrintConfig = PRINT,
                 text_heights: dict[str, float] | None = None) -> list[str]:
    """Gaps over max_block_gap_mm, other than those above a block named in free_gap_above."""
    limit = config.max_block_gap_mm
    return [f"page {g.page}: {round(g.gap_mm, 1):g} mm between {g.above!r} and {g.below!r}, the limit is {_num(limit)} mm"
            for g in block_gaps(positions, template, text_heights)
            if g.gap_mm > limit + EPS and g.below not in positions.free_gap_above]

