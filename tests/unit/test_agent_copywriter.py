"""The Copywriter agent with a FakeLLM: which slots it owns, what it sends, what it keeps, how it fails. No network."""
import json
import logging
from pathlib import Path

import pytest

from brochure.agents import TASKS
from brochure.agents.copywriter import PROMPT_FILE, TASK_SPEC, CopyInputs, copy_task_spec, copywriter_agent, owned_slots
from brochure.contracts.images import ImageTag
from brochure.llm import FakeLLM, LLMBadReply, LLMError, LLMRateLimited
from brochure.pipeline import load_sample_data
from brochure.verbatim import VERBATIM_SLOTS
from tests.support import GOOD_COPY as GOOD, qa_issue, sample_state

ROOT = Path(__file__).parents[2]
TEMPLATE = load_sample_data().template
OWNED = {
    "cover_tagline": 90, "overview_headline": 60, "overview_intro": 600, "overview_highlights": 240,
    "amenities_blurb": 250, "plan_note": 160, "about_headline": 60,
}

def inputs(**changes) -> CopyInputs:
    state = sample_state()
    tags = [ImageTag.model_validate(t) for t in json.loads((ROOT / "sample" / "image_tags.json").read_text(encoding="utf-8"))]
    base = dict(
        facts=state.project_facts, company_name=state.brand_kit.company_name, image_tags=tags, slots=owned_slots(TEMPLATE)
    )
    return CopyInputs(**{**base, **changes})


def run(reply=GOOD, **changes):
    llm = FakeLLM({"copy.write": reply})
    return copywriter_agent(inputs(**changes), llm), llm


def first_payload(llm) -> dict:
    assert llm.calls, "the model was never called"
    return llm.calls[0].payload


# --- which slots the copywriter owns ---------------------------------------------------------------------------------

def test_it_owns_every_text_slot_that_code_does_not_fill_verbatim_and_no_other():
    owned = owned_slots(TEMPLATE)
    assert {s.id: s.char_budget for s in owned} == OWNED
    text_slots = {s.id for s in TEMPLATE.slots if s.type == "text"}
    assert text_slots == set(OWNED) | set(VERBATIM_SLOTS)
    assert not set(OWNED) & set(VERBATIM_SLOTS)


def test_the_task_schema_is_strict_with_one_required_string_property_per_owned_slot_and_nothing_about_length():
    schema = TASK_SPEC.schema
    assert schema["type"] == "object"
    assert schema["additionalProperties"] is False
    assert schema["properties"] == {slot_id: {"type": "string"} for slot_id in OWNED}
    assert schema["required"] == list(OWNED)


def test_the_schema_follows_the_slots_it_is_given():
    spec = copy_task_spec([s for s in owned_slots(TEMPLATE) if s.id in ("cover_tagline", "plan_note")])
    assert list(spec.schema["properties"]) == ["cover_tagline", "plan_note"]
    assert spec.schema["required"] == ["cover_tagline", "plan_note"]


def test_the_real_client_knows_the_task_with_the_prompt_file_as_its_system_message():
    assert TASKS["copy.write"] is TASK_SPEC
    assert TASK_SPEC.system == PROMPT_FILE.read_text(encoding="utf-8").strip()


# --- the call ----------------------------------------------------------------------------------------------------------

def test_one_copy_write_call_without_images_and_the_text_of_every_owned_slot_comes_back():
    copy, llm = run()
    assert [(c.task, c.images) for c in llm.calls] == [("copy.write", [])]
    assert copy == GOOD
    assert list(copy) == list(OWNED)


def test_text_is_stripped_and_a_slot_the_code_fills_verbatim_is_never_in_the_result_even_if_the_model_writes_it():
    reply = {**GOOD, "cover_tagline": "  Aurelia Heights \n", "disclaimer": "Buy now", "rera_number": "P1", "about_text": "x"}
    copy, _ = run(reply)
    assert copy["cover_tagline"] == "Aurelia Heights"
    assert not set(copy) & set(VERBATIM_SLOTS)
    assert set(copy) == set(OWNED)


def test_the_payload_has_the_facts_the_images_the_tone_and_only_the_owned_slots():
    state = sample_state()
    _, llm = run()
    payload = first_payload(llm)
    assert set(payload) == {"project", "company_name", "images", "tone_notes", "slots"}
    assert payload["project"] == state.project_facts.model_dump(exclude={"tone_notes"})
    assert payload["company_name"] == "Kestrel Urbanscapes"
    assert payload["tone_notes"] == state.project_facts.tone_notes
    assert payload["slots"] == [
        {"id": s.id, "page": s.page, "char_budget": s.char_budget, "max_words": s.char_budget // 7, "comment": s.comment}
        for s in owned_slots(TEMPLATE)
    ]
    assert {s["id"] for s in payload["slots"]}.isdisjoint(VERBATIM_SLOTS)


def test_the_payload_carries_each_images_kind_subject_and_features_and_nothing_else_no_paths():
    _, llm = run()
    images = first_payload(llm)["images"]
    assert len(images) == 12
    assert all(set(i) == {"kind", "subject", "features"} for i in images)
    assert images[0] == {"kind": "render", "subject": "Twin residential towers at dusk, seen from the podium garden",
                         "features": ["tower", "facade", "dusk sky", "landscaping"]}
    assert ".jpg" not in json.dumps(first_payload(llm))


def test_the_payload_has_no_verbatim_text_from_the_brand_kit():
    state = sample_state()
    _, llm = run()
    text = json.dumps(first_payload(llm))
    for secret in (state.brand_kit.disclaimer, state.brand_kit.about_text, state.brand_kit.contact.phone, state.brand_kit.contact.email):
        assert secret not in text


def test_an_empty_tone_is_sent_as_an_empty_string():
    state = sample_state()
    facts = state.project_facts.model_copy(update={"tone_notes": ""})
    _, llm = run(facts=facts)
    assert first_payload(llm)["tone_notes"] == ""


# --- failing slots are asked for again, once, and only those -----------------------------------------------------------

class Script:
    """An LLMClient that plays one scripted answer per call (a dict is returned, an exception is raised)."""

    def __init__(self, *answers):
        self.answers, self.calls = list(answers), []

    def complete(self, task, payload, images=None):
        self.calls.append((task, payload, images))
        assert len(self.calls) <= len(self.answers), f"unexpected call number {len(self.calls)}"
        answer = self.answers[len(self.calls) - 1]
        if isinstance(answer, Exception):
            raise answer
        return answer


def play(*answers, **changes):
    llm = Script(*answers)
    return copywriter_agent(inputs(**changes), llm), llm


TOO_LONG = "A" * 91  # cover_tagline has 90 characters


def test_an_over_budget_slot_is_asked_for_again_and_the_second_text_is_used():
    copy, llm = play({**GOOD, "cover_tagline": TOO_LONG}, GOOD)
    assert len(llm.calls) == 2
    assert copy == GOOD


def test_an_empty_slot_is_asked_for_again():
    copy, llm = play({**GOOD, "plan_note": "  "}, GOOD)
    assert len(llm.calls) == 2
    assert copy == GOOD


def test_a_reply_without_a_slot_or_with_a_non_string_for_it_counts_as_a_failure_of_that_slot():
    incomplete = {k: v for k, v in GOOD.items() if k != "plan_note"}
    copy, llm = play({**incomplete, "cover_tagline": 7}, GOOD)
    assert len(llm.calls) == 2
    assert [s["id"] for s in llm.calls[1][1]["slots"]] == ["cover_tagline", "plan_note"]
    assert copy == GOOD


def test_the_second_call_sends_only_the_failing_slots_with_the_reason_for_each_and_the_rest_unchanged():
    _, llm = play({**GOOD, "cover_tagline": TOO_LONG, "plan_note": ""}, GOOD)
    first, second = llm.calls[0][1], llm.calls[1][1]
    assert "problems" not in first
    assert [s["id"] for s in second["slots"]] == ["cover_tagline", "plan_note"]
    assert set(second["problems"]) == {"plan_note"}  # wrong in content: written again with the reason
    assert "empty" in second["problems"]["plan_note"]
    assert set(second["shorten"]) == {"cover_tagline"}  # only too long: edited, with its previous text
    assert "91" in second["shorten"]["cover_tagline"]["problem"] and "90" in second["shorten"]["cover_tagline"]["problem"]
    assert {k: v for k, v in second.items() if k not in ("slots", "problems", "shorten")} == {k: v for k, v in first.items() if k != "slots"}


def test_slots_that_passed_the_first_time_are_kept_whatever_the_second_reply_says_about_them():
    second = {**GOOD, "cover_tagline": "Aurelia Heights, Pune", "plan_note": "REWRITTEN", "about_headline": "x" * 500}
    copy, _ = play({**GOOD, "cover_tagline": TOO_LONG}, second)
    assert copy["cover_tagline"] == "Aurelia Heights, Pune"
    assert copy["plan_note"] == GOOD["plan_note"]
    assert copy["about_headline"] == GOOD["about_headline"]


def test_a_second_reply_that_fixes_one_slot_and_not_the_other_keeps_the_fixed_one():
    copy, llm = play({**GOOD, "cover_tagline": TOO_LONG, "plan_note": ""}, {**GOOD, "plan_note": ""})
    assert len(llm.calls) == 2
    assert copy["cover_tagline"] == GOOD["cover_tagline"]
    assert "plan_note" not in copy


# --- a slot that still fails is left out, with one warning --------------------------------------------------------------

def warnings(caplog) -> list[str]:
    return [r.getMessage() for r in caplog.records if r.levelno >= logging.WARNING]


def test_a_slot_that_fails_twice_is_left_out_and_exactly_one_warning_says_which_and_why(caplog):
    bad = {**GOOD, "cover_tagline": TOO_LONG}
    copy, llm = play(bad, bad)
    assert len(llm.calls) == 2  # asked once more, not again
    assert set(copy) == set(OWNED) - {"cover_tagline"}
    (message,) = warnings(caplog)
    assert "cover_tagline" in message and "91 characters, the limit is 90" in message


def test_several_slots_that_fail_twice_share_one_warning(caplog):
    bad = {**GOOD, "cover_tagline": TOO_LONG, "plan_note": "", "about_headline": "Near Zorbaville"}
    copy, _ = play(bad, bad)
    assert set(copy) == set(OWNED) - {"cover_tagline", "plan_note", "about_headline"}
    (message,) = warnings(caplog)
    assert all(slot_id in message for slot_id in ("cover_tagline", "plan_note", "about_headline"))
    assert "Zorbaville" in message and "empty" in message


def test_the_reason_in_the_warning_is_the_one_from_the_second_attempt(caplog):
    play({**GOOD, "cover_tagline": TOO_LONG}, {**GOOD, "cover_tagline": "Heights in Zorbaville"})
    (message,) = warnings(caplog)
    assert "Zorbaville" in message and "91 characters" not in message


def test_no_warning_when_every_slot_passes(caplog):
    caplog.set_level(logging.INFO, logger="brochure.agents.copywriter")
    play(GOOD)
    assert warnings(caplog) == []


# --- the client fails: the run never crashes ---------------------------------------------------------------------------

@pytest.mark.parametrize("error", [
    LLMRateLimited("rate limit still hit after 3 attempts"),
    LLMError("HTTP 500 from the provider"),
])  # LLMBadReply is not here: it is asked once more, see below
def test_a_client_error_on_the_first_call_gives_no_copy_and_one_warning_without_raising(error, caplog):
    copy, llm = play(error)
    assert copy == {}
    assert len(llm.calls) == 1
    (message,) = warnings(caplog)
    assert str(error) in message
    assert all(slot_id in message for slot_id in OWNED)


def test_a_client_error_on_the_second_call_keeps_the_slots_that_passed_and_one_warning_names_the_rest(caplog):
    copy, llm = play({**GOOD, "cover_tagline": TOO_LONG}, LLMRateLimited("rate limit"))
    assert copy == {k: v for k, v in GOOD.items() if k != "cover_tagline"}
    (message,) = warnings(caplog)
    assert "cover_tagline" in message and "91 characters" in message and "rate limit" in message
    assert "plan_note" not in message  # it passed


def test_it_never_asks_again_after_a_client_error():
    _, llm = play(LLMError("down"), GOOD)
    assert len(llm.calls) == 1


# --- the QA loop sends the run back ------------------------------------------------------------------------------------

def test_issues_routed_to_the_copywriter_are_in_the_payload_with_their_page_check_and_note():
    issues = [qa_issue("copywriter", note="the intro mentions a nearby mall that is not on the page"),
              qa_issue("copywriter", note="the headline is too long on page 1")]
    _, llm = play(GOOD, qa_issues=issues)
    assert llm.calls[0][1]["qa_issues"] == [
        {"page": 1, "check": "stub", "note": "the intro mentions a nearby mall that is not on the page"},
        {"page": 1, "check": "stub", "note": "the headline is too long on page 1"},
    ]


def test_without_qa_issues_the_payload_has_no_qa_issues_key():
    _, llm = play(GOOD)
    assert "qa_issues" not in llm.calls[0][1]


def test_the_qa_issues_are_sent_again_with_the_second_call():
    _, llm = play({**GOOD, "cover_tagline": TOO_LONG}, GOOD, qa_issues=[qa_issue("copywriter", note="tone")])
    assert llm.calls[1][1]["qa_issues"] == llm.calls[0][1]["qa_issues"]


# --- each kind of check is wired in ------------------------------------------------------------------------------------

@pytest.mark.parametrize("bad, reason", [
    ("Homes of 900 sq ft", "900"),                       # a number the facts do not have
    ("Five floors above the metro", "Five"),             # a number word the facts do not have
    ("Near Hinjewadi and the metro", "Hinjewadi"),       # an invented place
    ("Priced for families", "money"),                    # money
    ("The best address in Pune", "best"),                # a superlative
])
def test_a_slot_that_breaks_a_content_check_is_asked_for_again_with_that_reason(bad, reason):
    copy, llm = play({**GOOD, "cover_tagline": bad}, GOOD)
    assert len(llm.calls) == 2
    assert reason in llm.calls[1][1]["problems"]["cover_tagline"]
    assert copy["cover_tagline"] == GOOD["cover_tagline"]


def test_the_copy_task_asks_for_low_reasoning_so_a_reasoning_model_has_room_left_to_write_the_json():
    assert TASK_SPEC.reasoning_effort == "low"
    assert copy_task_spec(owned_slots(TEMPLATE)).reasoning_effort == "low"


def test_the_prompt_asks_for_sentence_case_headlines_because_the_name_check_rejects_title_case():
    prompt = PROMPT_FILE.read_text(encoding="utf-8")
    assert "sentence case" in prompt
    assert "Title Case" in prompt  # shown as the thing not to do


def test_the_prompt_asks_for_headroom_under_each_budget():
    assert "85%" in PROMPT_FILE.read_text(encoding="utf-8")


def test_the_prompt_forbids_the_details_the_code_checks_cannot_see_views_materials_and_travel_times():
    prompt = PROMPT_FILE.read_text(encoding="utf-8")
    assert "views" in prompt and "walking distance" in prompt


def test_the_payload_kinds_are_the_tags_kinds_so_the_model_can_tell_a_render_from_a_plan():
    _, llm = run()
    kinds = [i["kind"] for i in first_payload(llm)["images"]]
    tags = inputs().image_tags
    assert kinds == [t.kind for t in tags]
    assert {"render", "floor_plan", "map"} <= set(kinds)


def test_no_code_check_looks_for_artists_impression_so_a_plan_called_one_is_still_accepted():
    # The wording rule lives in the prompt only; the live test reads the real copy.
    wrong = "The floor plans are an artist's impression of the layouts."
    copy, llm = play({**GOOD, "plan_note": wrong})
    assert copy["plan_note"] == wrong
    assert len(llm.calls) == 1


def test_the_prompt_says_only_renders_are_an_artists_impression():
    rule = next(line for line in PROMPT_FILE.read_text(encoding="utf-8").splitlines() if line.startswith("10."))
    for word in ("render", "photo", "floor_plan", "map", "artist's impression"):
        assert word in rule
    assert "never" in rule


# --- the returned copy is normalised ---------------------------------------------------------------------------------

def test_the_returned_copy_has_plain_spaces_and_hyphens_whatever_the_model_wrote():
    typed = {
        **GOOD,
        "overview_highlights": "2\u00a0BHK homes of 780\u202fsq\u202fft\nCo\u2011working lounge\nPossession Dec\u20092028\nHigh\u2010speed lifts",
        "plan_note": "Areas shown are carpet areas\u2003only. Children\u2019s play area.",
    }
    copy, llm = play(typed)
    assert len(llm.calls) == 1  # nothing failed: the typographic characters were not a reason to retry
    assert copy["overview_highlights"] == "2 BHK homes of 780 sq ft\nCo-working lounge\nPossession Dec 2028\nHigh-speed lifts"
    assert copy["plan_note"] == "Areas shown are carpet areas only. Children\u2019s play area."


def test_the_budget_is_checked_on_the_normalised_text_which_is_the_text_that_is_returned():
    copy, _ = play({**GOOD, "cover_tagline": "Aurelia\u202fHeights"})
    assert copy["cover_tagline"] == "Aurelia Heights" and len(copy["cover_tagline"]) <= OWNED["cover_tagline"]


def test_the_prompt_says_each_highlight_line_states_a_fact_from_the_project_not_a_picture():
    prompt = PROMPT_FILE.read_text(encoding="utf-8")
    rule = next(line for line in prompt.splitlines() if "overview_highlights" in line and line[0].isdigit())
    for word in ("fact", "configuration", "location", "possession", "amenity", "landmark", "picture"):
        assert word in rule


# --- a reply that is not valid JSON is asked for once more, as the Brief agent does ----------------------------------------

BAD = LLMBadReply("the model's reply is not valid JSON: '{\"cover_tagline\": '")


def test_a_bad_reply_is_asked_again_once_with_the_error_and_the_second_reply_is_used(caplog):
    copy, llm = play(BAD, GOOD)
    assert len(llm.calls) == 2
    assert copy == GOOD
    first, second = llm.calls[0][1], llm.calls[1][1]
    assert "previous_error" not in first
    assert "not valid JSON" in second["previous_error"]
    assert {k: v for k, v in second.items() if k != "previous_error"} == first
    assert warnings(caplog) == []


def test_a_second_bad_reply_falls_back_like_any_other_error_with_one_warning(caplog):
    copy, llm = play(BAD, LLMBadReply("still not JSON"), GOOD)
    assert copy == {}
    assert len(llm.calls) == 2  # not a third
    (message,) = warnings(caplog)
    assert "still not JSON" in message and all(slot_id in message for slot_id in OWNED)


def test_a_bad_reply_to_the_second_attempt_is_also_asked_again_and_keeps_the_shorten_list():
    copy, llm = play({**GOOD, "cover_tagline": TOO_LONG}, BAD, GOOD)
    assert len(llm.calls) == 3
    assert copy == GOOD
    second, third = llm.calls[1][1], llm.calls[2][1]
    assert third["shorten"] == second["shorten"] and "previous_error" in third
    assert [s["id"] for s in third["slots"]] == ["cover_tagline"]


def test_two_bad_replies_to_the_second_attempt_keep_what_passed_and_leave_the_rest_out(caplog):
    copy, llm = play({**GOOD, "cover_tagline": TOO_LONG}, BAD, LLMBadReply("again"))
    assert len(llm.calls) == 3
    assert copy == {k: v for k, v in GOOD.items() if k != "cover_tagline"}
    (message,) = warnings(caplog)
    assert "cover_tagline" in message and "91 characters" in message and "again" in message


def test_only_a_bad_reply_is_asked_again_a_rate_limit_or_http_error_is_not():
    for error in (LLMRateLimited("rate limit"), LLMError("HTTP 500")):
        _, llm = play(error, GOOD)
        assert len(llm.calls) == 1


def test_the_prompt_explains_previous_error():
    assert "previous_error" in PROMPT_FILE.read_text(encoding="utf-8")


# --- word limits in the payload -------------------------------------------------------------------------------------------

MAX_WORDS = {"cover_tagline": 12, "overview_headline": 8, "overview_intro": 85, "overview_highlights": 34,
             "amenities_blurb": 35, "plan_note": 22, "about_headline": 8}


def test_each_slot_is_sent_with_max_words_derived_from_its_char_budget():
    from brochure.agents.copy_checks import max_words

    _, llm = run()
    slots = first_payload(llm)["slots"]
    assert {s["id"]: s["max_words"] for s in slots} == MAX_WORDS
    assert all(s["max_words"] == max_words(s["char_budget"]) for s in slots)
    assert all(set(s) == {"id", "page", "char_budget", "max_words", "comment"} for s in slots)


def test_the_prompt_tells_the_model_to_stay_under_max_words():
    prompt = PROMPT_FILE.read_text(encoding="utf-8")
    rule = next(line for line in prompt.splitlines() if line.startswith("9."))
    assert "max_words" in rule and "char_budget" in rule


# --- a slot that is only too long is edited, not rewritten --------------------------------------------------------------------

SENTENCE = "The towers stand around a landscaped podium garden."


def long_intro(extra: int) -> str:
    return GOOD["overview_intro"] + (" " + SENTENCE) * extra


def test_a_slot_that_fails_only_on_length_is_sent_back_with_its_previous_text_to_shorten():
    _, llm = play({**GOOD, "cover_tagline": TOO_LONG}, GOOD)
    second = llm.calls[1][1]
    assert second["shorten"] == {"cover_tagline": {"previous_text": TOO_LONG, "problem": second["shorten"]["cover_tagline"]["problem"]}}
    assert "91 characters" in second["shorten"]["cover_tagline"]["problem"]
    assert "problems" not in second
    assert [s["id"] for s in second["slots"]] == ["cover_tagline"]


def test_a_slot_that_is_wrong_in_content_as_well_as_too_long_gets_the_full_retry_not_the_edit():
    wrong = "Near Zorbaville " + "a" * 100
    _, llm = play({**GOOD, "cover_tagline": wrong}, GOOD)
    second = llm.calls[1][1]
    assert "shorten" not in second
    assert "Zorbaville" in second["problems"]["cover_tagline"] and "characters" in second["problems"]["cover_tagline"]


def test_length_and_content_failures_in_one_reply_are_split_between_shorten_and_problems():
    _, llm = play({**GOOD, "cover_tagline": TOO_LONG, "plan_note": "The best homes"}, GOOD)
    second = llm.calls[1][1]
    assert set(second["shorten"]) == {"cover_tagline"}
    assert set(second["problems"]) == {"plan_note"}
    assert [s["id"] for s in second["slots"]] == ["cover_tagline", "plan_note"]


def test_the_shortened_text_from_the_second_reply_is_used():
    copy, _ = play({**GOOD, "cover_tagline": TOO_LONG}, {**GOOD, "cover_tagline": "Light and air at Aurelia Heights."})
    assert copy["cover_tagline"] == "Light and air at Aurelia Heights."


def test_the_prompt_explains_shorten():
    prompt = PROMPT_FILE.read_text(encoding="utf-8")
    assert '"shorten"' in prompt and "previous_text" in prompt and "cutting" in prompt


# --- the safety net: trim to whole sentences ------------------------------------------------------------------------------------

def expected_trim(extra_available: int) -> str:
    text = GOOD["overview_intro"]
    while len(text + " " + SENTENCE) <= OWNED["overview_intro"] and extra_available > 0:
        text, extra_available = text + " " + SENTENCE, extra_available - 1
    return text


def test_a_slot_still_over_budget_after_the_retry_is_trimmed_to_whole_sentences_that_fit(caplog):
    caplog.set_level(logging.INFO, logger="brochure.agents.copywriter")
    copy, llm = play({**GOOD, "overview_intro": long_intro(8)}, {**GOOD, "overview_intro": long_intro(12)})
    trimmed = copy["overview_intro"]
    assert len(llm.calls) == 2
    assert trimmed == expected_trim(12) and len(trimmed) <= 600 < len(trimmed + " " + SENTENCE)
    assert trimmed.endswith(".")
    assert warnings(caplog) == []
    assert any("trimmed slot overview_intro" in r.getMessage() and r.levelno == logging.INFO for r in caplog.records)


def test_a_trimmed_text_is_checked_again_so_a_bad_sentence_is_not_kept(caplog):
    bad = long_intro(0) + " It stands near Zorbaville." + (" " + SENTENCE) * 12
    copy, _ = play({**GOOD, "overview_intro": bad}, {**GOOD, "overview_intro": bad})
    assert copy["overview_intro"] == GOOD["overview_intro"]  # everything from the bad sentence on is cut
    assert warnings(caplog) == []


def test_a_headline_slot_is_never_trimmed_and_is_left_out_with_the_warning(caplog):
    two_sentences = "Calm homes by the park. " + "A" * 80
    for slot_id in ("cover_tagline", "overview_headline", "about_headline"):
        caplog.clear()
        reply = {**GOOD, slot_id: two_sentences}
        copy, _ = play(reply, reply)
        assert slot_id not in copy
        (message,) = warnings(caplog)
        assert slot_id in message


def test_a_slot_where_not_even_the_first_sentence_fits_is_left_out_with_the_warning(caplog):
    one_long_sentence = "Aurelia Heights " + "has homes " * 70 + "for families."
    copy, _ = play({**GOOD, "overview_intro": one_long_sentence}, {**GOOD, "overview_intro": one_long_sentence})
    assert "overview_intro" not in copy
    (message,) = warnings(caplog)
    assert "overview_intro" in message


def test_when_the_second_call_fails_the_first_texts_that_can_be_trimmed_are_trimmed(caplog):
    copy, llm = play({**GOOD, "overview_intro": long_intro(12), "cover_tagline": TOO_LONG}, LLMRateLimited("rate limit"))
    assert copy["overview_intro"] == expected_trim(12)
    assert "cover_tagline" not in copy
    (message,) = warnings(caplog)
    assert "cover_tagline" in message and "overview_intro" not in message and "rate limit" in message


def test_the_single_line_slots_are_the_headlines_taglines_and_titles():
    from brochure.agents.copywriter import is_single_line

    ids = {s.id: is_single_line(s) for s in owned_slots(TEMPLATE)}
    assert ids == {"cover_tagline": True, "overview_headline": True, "about_headline": True, "overview_intro": False,
                   "overview_highlights": False, "amenities_blurb": False, "plan_note": False}
