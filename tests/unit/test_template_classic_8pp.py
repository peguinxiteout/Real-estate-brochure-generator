from pathlib import Path

import pytest

from brochure.print_config import PRINT
from brochure.slots import load_slots

SLOTS_JSON = Path(__file__).parents[2] / "templates" / "classic-8pp" / "slots.json"


@pytest.fixture(scope="module")
def template():
    return load_slots(SLOTS_JSON)


def test_every_page_from_1_to_8_has_slots(template):
    assert template.template_id == "classic-8pp"
    assert sorted({s.page for s in template.slots}) == list(range(1, 9))


def test_cover_hero_is_a_full_page_slot_bleeding_on_all_four_edges(template):
    hero = template.get("hero")
    assert (hero.page, hero.type) == (1, "image")
    assert sorted(hero.bleed_edges) == ["bottom", "left", "right", "top"]
    assert (hero.width_mm, hero.height_mm) == (PRINT.page_width_mm, PRINT.page_height_mm)
    assert hero.min_px == (2552, 3579)


def test_back_cover_has_the_rera_number_and_a_provisional_25mm_qr(template):
    back = {s.id: s for s in template.slots if s.page == 8}
    assert back["rera_number"].type == "text"
    qr = back["rera_qr"]
    assert (qr.type, qr.width_mm, qr.height_mm) == ("qr", 25, 25)
    assert "PROVISIONAL" in qr.comment


def test_there_is_no_pricing_slot(template):
    assert [s.id for s in template.slots if "price" in s.id or "pricing" in s.id] == []


def test_every_slot_fits_inside_an_a4_page(template):
    too_big = [s.id for s in template.slots if s.width_mm > PRINT.page_width_mm or s.height_mm > PRINT.page_height_mm]
    assert too_big == []
