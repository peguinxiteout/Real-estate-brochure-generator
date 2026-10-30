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
