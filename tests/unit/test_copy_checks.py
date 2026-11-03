"""The code checks on a slot's copy: budget, numbers, names, money and superlatives. Pure logic, no model."""
import pytest

from brochure.agents.copy_checks import known_from, problems
from tests.support import sample_state

STATE = sample_state()
KNOWN = known_from(STATE.project_facts, STATE.brand_kit.company_name)


def check(text, budget=500):
    return problems(text, budget, KNOWN)


def test_plain_copy_within_the_budget_has_no_problems():
    assert check("Light, air and green space, close to the metro.") == []


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
    reasons = check("Just 5 floors above the metro.")
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
    reasons = check("Five floors above the metro")
    assert len(reasons) == 1 and "five" in reasons[0].lower()


def test_a_number_word_is_matched_to_the_same_number_written_in_digits():
    assert check("two towers of three BHK homes") == []  # 2 and 3 are in the facts (2 BHK, 3 BHK)


def test_number_words_run_from_one_to_twenty_whatever_their_case():
    assert len(check("TWENTY homes")) == 1
    assert len(check("One home")) == 1
    assert check("a stone wall, alone, someone, phone and money") == []  # whole words only


def test_a_number_word_in_the_facts_counts():
    facts = STATE.project_facts.model_copy(update={"amenities": ["Four lifts"]})
    known = known_from(facts, "Kestrel Urbanscapes")
    assert problems("Four lifts for the tower", 100, known) == []


def test_each_distinct_number_is_reported_once_in_one_reason():
    reasons = check("5 or 5 or 6 or nine")
    assert len(reasons) == 1
    assert reasons[0].count("5") == 1 and "6" in reasons[0] and "nine" in reasons[0]


# --- names: a capitalised word inside a sentence must come from the facts, the company name or the allow-list ---------

def test_an_invented_place_name_fails_and_the_reason_names_it():
    reasons = check("Close to Hinjewadi and the metro")
    assert len(reasons) == 1 and "Hinjewadi" in reasons[0] and "facts" in reasons[0]


@pytest.mark.parametrize("text", [
    "Close to Meridian Metro Station",   # a landmark
    "Near Lakeside Hospital and Orchard International School",
    "On Meridian Park Road in Pune, Maharashtra",   # the location and the RERA state
    "Aurelia Heights has a Clubhouse",         # the project name; an amenity
    "Built by Kestrel Urbanscapes",            # the company name
    "Handed over by KESTREL URBANSCAPES",      # any case
    "Kestrel's team and Pune's skyline",       # a possessive is the same name
])
def test_a_name_from_the_facts_or_the_company_name_passes(text):
    assert check(text) == []


def test_the_first_word_of_a_sentence_or_line_is_not_checked_as_a_name():
    assert check("Hinjewadi is far away") == []
    assert check("Calm streets. Zorbaville is a place") == []
    assert check("Is it quiet? Yes. Tranquil, too! Serene") == []
    assert check("Two towers\nLandscaped garden\n- Jogging track\n\u2022 Greenery") == []
    assert check('"Peaceful" living') == []


def test_a_capitalised_word_after_a_comma_or_a_colon_is_checked():
    assert len(check("Calm, Zorbaville and quiet")) == 1
    assert len(check("Where: Zorbaville")) == 1


def test_lowercase_words_are_never_checked_as_names():
    assert check("a splendid vista over rooftops") == []


def test_common_capitalised_words_from_the_allow_list_pass():
    assert check("Handover in March, RERA registered, 2 BHK homes, sq ft and km") == []


def test_unknown_all_caps_words_fail_like_any_other_name():
    assert len(check("Fitted with AC units")) == 1


def test_several_invented_names_are_listed_once_each_in_one_reason():
    reasons = check("Near Zorbaville, Hinjewadi and Zorbaville")
    assert len(reasons) == 1
    assert reasons[0].count("Zorbaville") == 1 and "Hinjewadi" in reasons[0]


def test_the_allow_list_is_a_data_file_shipped_with_the_package():
    import tomllib
    from pathlib import Path

    from brochure.agents.copy_checks import DATA_DIR

    assert (DATA_DIR / "copy_name_allowlist.txt").is_file()
    pyproject = tomllib.loads((Path(__file__).parents[2] / "pyproject.toml").read_text(encoding="utf-8"))
    assert "agents/data/*.txt" in pyproject["tool"]["setuptools"]["package-data"]["brochure"]


# --- money: no prices, currency or investment language ---------------------------------------------------------------

@pytest.mark.parametrize("word", ["\u20b9", "Rs", "INR", "lakh", "crore", "price", "EMI", "returns", "investment"])
def test_each_money_word_is_rejected_and_the_reason_names_it(word):
    reasons = check(f"Calm homes with {word} in the line")  # "Rs" or "EMI" is also an unknown name; that reason may come too
    assert any("money" in r and word in r for r in reasons)


def test_money_words_are_matched_as_whole_words_in_any_case():
    assert any("money" in r for r in check("The PRICE is a surprise"))
    assert any("money" in r for r in check("a good price"))
    assert check("Doors, stairs, pricey-free walls, an investigation and a priceless view") == []


def test_a_currency_symbol_is_rejected_even_when_a_digit_follows_it():
    assert any("money" in r for r in check("From \u20b95 only"))


def test_the_money_words_are_a_data_file():
    from brochure.agents.copy_checks import DATA_DIR

    words = (DATA_DIR / "copy_money_words.txt").read_text(encoding="utf-8")
    assert {"\u20b9", "Rs", "INR", "lakh", "crore", "price", "EMI", "returns", "investment"} <= set(words.split())


# --- superlatives and promises ---------------------------------------------------------------------------------------

BANNED = ["best", "No. 1", "number one", "largest", "finest", "guaranteed", "assured returns", "award-winning", "world-class", "unmatched"]


@pytest.mark.parametrize("phrase", BANNED)
def test_each_banned_phrase_is_rejected_and_the_reason_names_it(phrase):
    reasons = check(f"Homes that are {phrase} in the area")
    assert any("superlative" in r and phrase in r for r in reasons)


def test_banned_phrases_match_in_any_case_and_inside_a_hyphenated_word():
    assert any("best" in r for r in check("THE BEST views"))
    assert any("best" in r for r in check("a best-in-class pool"))
    assert any("world-class" in r for r in check("World-Class amenities"))
    assert any("number one" in r for r in check("a number   one address"))


def test_banned_phrases_are_whole_words_only():
    assert check("They bestow calm, with bestsellers and unmatchedly quiet corners") == []
    assert check("A bigger pool, the largely green podium") == []


def test_the_banned_phrases_are_a_data_file():
    from brochure.agents.copy_checks import DATA_DIR

    lines = (DATA_DIR / "copy_banned_phrases.txt").read_text(encoding="utf-8").splitlines()
    assert set(BANNED) <= {line.strip() for line in lines}


# --- found by the live run ---------------------------------------------------------------------------------------------

def test_a_title_cased_headline_is_rejected_and_the_reason_says_to_use_lower_case_for_words_that_are_not_names():
    reasons = check("Twin Towers Shine Over Pune")
    assert len(reasons) == 1
    assert "Towers" in reasons[0] and "Shine" in reasons[0] and "Pune" not in reasons[0]
    assert "lower case" in reasons[0]


@pytest.mark.parametrize("separator", ["\u00a0", "\u202f", "\u2009"])
def test_a_thousands_group_split_by_a_non_breaking_or_thin_space_is_one_number(separator):
    assert check(f"Homes of 1{separator}090 sq ft") == []
    assert len(check(f"Homes of 1{separator}091 sq ft")) == 1


def test_the_over_budget_reason_gives_a_target_below_the_limit_because_a_model_cannot_count_characters():
    (reason,) = check("a" * 630, budget=600)
    assert "630 characters, the limit is 600" in reason
    assert "510" in reason  # 85% of the budget: the length to aim for


# --- normalising: typographic spaces and hyphens become plain ones before the checks ------------------------------------

from brochure.agents.copy_checks import normalise_text  # noqa: E402


def test_a_narrow_no_break_space_u202f_becomes_a_plain_space():
    assert normalise_text("780\u202fsq\u202fft") == "780 sq ft"


def test_a_no_break_space_u00a0_becomes_a_plain_space():
    assert normalise_text("2\u00a0BHK") == "2 BHK"


def test_a_thin_space_u2009_becomes_a_plain_space():
    assert normalise_text("Dec\u20092028") == "Dec 2028"


@pytest.mark.parametrize("space", ["\u2002", "\u2003", "\u2007", "\u200a", "\u205f", "\u3000", "\u1680"])
def test_any_other_unicode_space_separator_becomes_a_plain_space(space):
    assert normalise_text(f"a{space}b") == "a b"


def test_a_hyphen_u2010_becomes_a_plain_hyphen():
    assert normalise_text("co\u2010working") == "co-working"


def test_a_non_breaking_hyphen_u2011_becomes_a_plain_hyphen():
    assert normalise_text("high\u2011speed lifts") == "high-speed lifts"


def test_curly_quotes_and_apostrophes_and_dashes_are_kept():
    text = "Children\u2019s \u201cplay\u201d area \u2013 and \u2018more\u2019 \u2014 done"
    assert normalise_text(text) == text


def test_newlines_and_plain_text_are_untouched():
    assert normalise_text("one\nline two\ttab") == "one\nline two\ttab"


def test_the_checks_see_normalised_text_so_a_sentence_start_after_an_em_space_is_found():
    from tests.unit.test_agent_copywriter import GOOD, play  # the agent normalises before it checks

    copy, llm = play({**GOOD, "cover_tagline": "Calm streets.\u2003Zorbaville is near"})
    assert len(llm.calls) == 1
    assert copy["cover_tagline"] == "Calm streets. Zorbaville is near"


# --- word limits: a model counts words, not characters -----------------------------------------------------------------

from brochure.agents import copy_checks  # noqa: E402


def test_the_word_limit_is_the_char_budget_divided_by_one_constant_rounded_down():
    assert copy_checks.CHARS_PER_WORD == 7
    assert [copy_checks.max_words(b) for b in (600, 250, 240, 160, 90, 60, 40, 7, 6)] == [85, 35, 34, 22, 12, 8, 5, 1, 0]


def test_the_word_limit_follows_the_constant(monkeypatch):
    monkeypatch.setattr(copy_checks, "CHARS_PER_WORD", 5)
    assert copy_checks.max_words(600) == 120


# --- more banned phrases: the travel-time and location clichés -------------------------------------------------------------

@pytest.mark.parametrize("phrase", ["heart of", "prime location", "minutes from", "minutes away", "walking distance", "short walk", "steps from", "stone's throw"])
def test_each_location_cliche_is_rejected_and_the_reason_names_it(phrase):
    reasons = check(f"Homes in the area, {phrase} the metro")
    assert any("superlative" in r and phrase in r for r in reasons)


def test_a_stones_throw_written_with_a_curly_apostrophe_is_rejected_too():
    assert any("stone's throw" in r for r in check("Homes a stone\u2019s throw from the metro"))


def test_the_new_phrases_are_whole_words_only():
    assert check("Hearts of oak, a primer location, minute detail, a walking track") == []


# --- trimming: the safety net keeps whole sentences from the start --------------------------------------------------

from brochure.agents.copy_checks import trim_to_budget  # noqa: E402

S1 = "Aurelia Heights has 2 and 3 BHK homes."          # 38 characters
S2 = "The podium garden sits at its centre."            # 37
S3 = "The metro station is 1.2 km away."                # 33


def trim(text, budget):
    return trim_to_budget(text, budget, KNOWN)


def test_it_keeps_the_longest_run_of_whole_sentences_from_the_start_that_fits():
    text = f"{S1} {S2} {S3}"
    assert trim(text, len(S1) + 1 + len(S2)) == f"{S1} {S2}"   # exactly fits two
    assert trim(text, len(S1) + 1 + len(S2) + 20) == f"{S1} {S2}"  # three do not fit
    assert trim(text, len(text) - 1) == f"{S1} {S2}"
    assert trim(text, len(S1)) == S1


def test_it_never_cuts_in_the_middle_of_a_sentence():
    assert trim(f"{S1} {S2}", len(S1) - 1) is None  # not even the first sentence fits
    assert trim("One long sentence with no end that goes on and on and on", 20) is None
    for budget in range(1, 120):
        result = trim(f"{S1} {S2} {S3}", budget)
        assert result is None or result in (S1, f"{S1} {S2}", f"{S1} {S2} {S3}")


def test_a_trimmed_text_is_checked_again_and_a_shorter_run_is_used_when_the_longer_one_fails():
    bad = "It stands near Zorbaville."
    text = f"{S1} {bad} {S3}"
    assert trim(text, len(S1) + 1 + len(bad)) == S1            # S1 + bad fits but names an unknown place
    assert trim(f"{bad} {S1}", 500) is None                    # the first sentence itself fails: nothing to keep


def test_it_cuts_at_the_end_of_a_line_too():
    lines = "Two towers of 2 and 3 BHK homes\nLandscaped podium garden\nGym and clubhouse\nJogging track"
    assert trim(lines, len("Two towers of 2 and 3 BHK homes\nLandscaped podium garden\nGym and clubhouse")) == (
        "Two towers of 2 and 3 BHK homes\nLandscaped podium garden\nGym and clubhouse")
    assert trim(lines, 60) == "Two towers of 2 and 3 BHK homes\nLandscaped podium garden"


def test_a_full_stop_inside_a_sentence_is_not_a_boundary():
    text = "Homes of 780 sq. ft. carpet area are ready by Dec 2028. The metro station is 1.2 km away."
    assert trim(text, 60) == "Homes of 780 sq. ft. carpet area are ready by Dec 2028."
    assert trim(text, 30) is None


def test_a_text_that_already_passes_is_returned_unchanged():
    assert trim(f"{S1} {S2}", 500) == f"{S1} {S2}"


from brochure.agents.copy_checks import fails_only_on_length  # noqa: E402


def test_a_text_that_is_only_too_long_fails_only_on_length():
    assert fails_only_on_length(f"{S1} {S2}", 50, KNOWN)


@pytest.mark.parametrize("text", [
    f"{S1} It stands near Zorbaville and is long enough to go over the budget.",   # a name as well
    f"{S1} The price is a surprise and the text is long enough to go over.",         # money as well
    f"{S1} There are 99 more homes and this makes the text go over the budget.",     # a number as well
])
def test_a_text_that_is_too_long_and_also_wrong_in_content_does_not_fail_only_on_length(text):
    assert len(text) > 60
    assert not fails_only_on_length(text, 60, KNOWN)


def test_a_text_within_the_budget_or_an_empty_one_does_not_fail_on_length():
    assert not fails_only_on_length(S1, 500, KNOWN)
    assert not fails_only_on_length("  ", 10, KNOWN)
