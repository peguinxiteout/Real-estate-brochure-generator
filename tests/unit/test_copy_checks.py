"""The code checks on a slot's copy: budget, numbers, names, money and superlatives. Pure logic, no model."""
import pytest

from brochure.agents.copy_checks import known_from, problems
from tests.support import sample_state

STATE = sample_state()
KNOWN = known_from(STATE.project_facts, STATE.brand_kit.company_name)


def check(text, budget=500):
    return problems(text, budget, KNOWN)


def test_plain_copy_within_the_budget_has_no_problems():
    assert check("Light, air and green space, a short walk from the metro.") == []


def test_text_longer_than_the_budget_fails_with_its_length_and_the_limit():
    reasons = check("a" * 41, budget=40)
    assert len(reasons) == 1 and "41" in reasons[0] and "40" in reasons[0]


def test_text_exactly_at_the_budget_is_fine():
    assert check("a" * 40, budget=40) == []


@pytest.mark.parametrize("text", ["", "   ", "\n"])
def test_empty_text_fails(text):
    reasons = check(text)
    assert len(reasons) == 1 and "empty" in reasons[0]
