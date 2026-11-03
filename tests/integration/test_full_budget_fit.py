"""Every text slot's height fits its full char_budget: filler of exactly char_budget characters, rendered with the real
fonts and template and measured with the same marks as the overflow check."""
import importlib
import math
from pathlib import Path

import pytest

from brochure.contracts.spec import BrochureSpec, PageSpec, SlotFill
from brochure.pipeline.stubs import load_sample_data
from brochure.print_config import PRINT
from brochure.render.html import PX_PER_MM, build_html, load_template
from tests.support import filler_text, sample_state

pytestmark = pytest.mark.integration

ROOT = Path(__file__).parents[2]
TEMPLATE = load_sample_data().template
TEXT_SLOTS = [s.id for s in TEMPLATE.slots if s.type == "text"]
# Slots written line by line, at the average line length of the sample: (characters per line, label of each line).
LINED = {
    "overview_highlights": (30, ""),
    "location_landmarks": (29, ""),
    "amenities_list": (16, ""),
    "config_table": (23, ""),
    "specs_list": (49, "Flooring: "),
    "contact_block": (33, ""),
}


def full_budget_text(slot_id: str, chars: int) -> str:
    line, label = LINED.get(slot_id, (None, ""))
    return filler_text(chars, line, label)


def measured(page_anchors: list[dict], slot_id: str) -> float:
    """The slot's text height in mm, from its marks; infinite when the text ran off its page, which loses the end mark."""
    for anchors in page_anchors:
        start, end = anchors.get(f"start-{slot_id}"), anchors.get(f"end-{slot_id}")
        if start is not None:
            return (end[1] - start[1]) / PX_PER_MM if end is not None else math.inf
    return math.inf


def full_budget_heights(budgets: dict[str, int] | None = None) -> dict[str, float]:
    """slot id -> measured mm of each text slot filled to its char_budget (or to the budget given here)."""
    from weasyprint import HTML

    state = sample_state()
    template = load_template("classic-8pp")
    pages = []
    for number in range(1, 9):
        slots = {s.id: SlotFill(text=full_budget_text(s.id, (budgets or {}).get(s.id, s.char_budget)))
                 for s in template.slots.slots if s.page == number and s.type == "text"}
        pages.append(PageSpec(layout_id=f"p{number}", slots=slots))
    spec = BrochureSpec(template_id="classic-8pp", pages=pages)
    html = build_html(spec, state.brand_kit, [], ROOT / "sample" / "images", brand_dir=ROOT / "sample")
    anchors = [p.anchors for p in HTML(string=html, base_url=str(template.directory)).render().pages]
    return {slot_id: measured(anchors, slot_id) for slot_id in TEXT_SLOTS}


@pytest.fixture(scope="module")
def heights():
    try:
        importlib.import_module("weasyprint")
    except Exception as exc:  # ModuleNotFoundError, or OSError when the Pango libraries are missing
        pytest.skip(f"WeasyPrint is not importable ({type(exc).__name__}). Run `brochure doctor` for the fix.")
    return full_budget_heights()


@pytest.mark.parametrize("slot_id", TEXT_SLOTS)
def test_full_budget_text_fits_the_slot(heights, slot_id):
    slot = TEMPLATE.get(slot_id)
    assert heights[slot_id] <= slot.height_mm + PRINT.text_overflow_tolerance_mm, (
        f"{slot.char_budget} characters are {heights[slot_id]:.1f} mm tall in a {slot.height_mm:g} mm slot")
