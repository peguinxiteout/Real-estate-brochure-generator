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


# --- numbers: every number in the copy must be one the facts contain -------------------------------------------------

def test_a_number_the_facts_do_not_contain_fails_and_the_reason_names_it():
    reasons = check("Just 5 minutes from the metro.")
    assert len(reasons) == 1 and "5" in reasons[0] and "facts" in reasons[0]


@pytest.mark.parametrize("text", ["Homes of 780 sq ft", "Homes of 1,090 sq ft", "Homes of 1090 sq ft", "1.2 km from the metro", "Also 2.50 km"])
def test_numbers_from_the_facts_pass_whatever_their_formatting(text):
    # 2.50 is 2.5, a landmark distance; 1,090 is the 3 BHK carpet area written with a thousands comma
    assert check(text) == []


def test_a_decimal_that_is_not_in_the_facts_fails():
    assert len(check("1.3 km from the metro")) == 1


def test_a_whole_number_matches_a_fact_written_with_a_decimal_point():
    assert check("4 km from the business park") == []  # the fact is 4.0


def test_a_number_inside_a_text_fact_counts_a_year_from_dec_2028_and_the_2_of_2_bhk():
    assert check("Ready by 2028 in 2 and 3 BHK sizes") == []
    assert len(check("Ready by 2029")) == 1


def test_the_digits_around_an_x_in_24x7_are_read_as_numbers_from_the_facts():
    assert check("Security 24x7") == []


def test_a_number_word_that_the_facts_do_not_contain_fails():
    reasons = check("Five minutes from the metro")
    assert len(reasons) == 1 and "five" in reasons[0].lower()


def test_a_number_word_is_matched_to_the_same_number_written_in_digits():
    assert check("two towers of three BHK homes") == []  # 2 and 3 are in the facts (2 BHK, 3 BHK)


def test_number_words_run_from_one_to_twenty_whatever_their_case():
    assert len(check("TWENTY homes")) == 1
    assert len(check("One home")) == 1
    assert check("a stone's throw, alone, someone, phone and money") == []  # whole words only


def test_a_number_word_in_the_facts_counts():
    facts = STATE.project_facts.model_copy(update={"amenities": ["Four lifts"]})
    known = known_from(facts, "Kestrel Urbanscapes")
    assert problems("Four lifts for the tower", 100, known) == []


def test_each_distinct_number_is_reported_once_in_one_reason():
    reasons = check("5 or 5 or 6 or nine")
    assert len(reasons) == 1
    assert reasons[0].count("5") == 1 and "6" in reasons[0] and "nine" in reasons[0]
