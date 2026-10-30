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
