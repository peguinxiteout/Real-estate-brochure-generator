"""sample/stub_copy.json goes through the same checks as the real Copywriter's text, so the sample never shows copy the
real step would refuse."""
import re

import pytest

from brochure.agents.copy_checks import known_from, problems
from brochure.agents.copywriter import owned_slots
from brochure.pipeline.stubs import load_sample_data
from tests.support import sample_state

DATA = load_sample_data()
STATE = sample_state()
KNOWN = known_from(STATE.project_facts, STATE.brand_kit.company_name)
OWNED = owned_slots(DATA.template)


def test_the_stub_copy_writes_every_owned_slot():
    assert {s.id for s in OWNED} <= set(DATA.copy)


@pytest.mark.parametrize("slot", OWNED, ids=lambda s: s.id)
def test_each_owned_slot_of_the_stub_copy_passes_the_copy_checks(slot):
    assert problems(DATA.copy[slot.id], slot.char_budget, KNOWN) == []


def test_the_about_headline_names_the_company_and_claims_no_history():
    headline = DATA.copy["about_headline"]
    assert STATE.brand_kit.company_name in headline
    assert not re.search(r"\d|\b(years?|decades?|since|established|fifteen|legacy|history)\b", headline, re.IGNORECASE)
