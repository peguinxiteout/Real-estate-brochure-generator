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
    "cover_title": 40, "cover_tagline": 90, "overview_headline": 60, "overview_intro": 600, "overview_highlights": 240,
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
    spec = copy_task_spec([s for s in owned_slots(TEMPLATE) if s.id in ("cover_title", "plan_note")])
    assert list(spec.schema["properties"]) == ["cover_title", "plan_note"]
    assert spec.schema["required"] == ["cover_title", "plan_note"]


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
    reply = {**GOOD, "cover_title": "  Aurelia Heights \n", "disclaimer": "Buy now", "rera_number": "P1", "about_text": "x"}
    copy, _ = run(reply)
    assert copy["cover_title"] == "Aurelia Heights"
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
        {"id": s.id, "page": s.page, "char_budget": s.char_budget, "comment": s.comment} for s in owned_slots(TEMPLATE)
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


TOO_LONG = "A" * 41  # cover_title has 40 characters


def test_an_over_budget_slot_is_asked_for_again_and_the_second_text_is_used():
    copy, llm = play({**GOOD, "cover_title": TOO_LONG}, GOOD)
    assert len(llm.calls) == 2
    assert copy == GOOD


def test_an_empty_slot_is_asked_for_again():
    copy, llm = play({**GOOD, "plan_note": "  "}, GOOD)
    assert len(llm.calls) == 2
    assert copy == GOOD


def test_a_reply_without_a_slot_or_with_a_non_string_for_it_counts_as_a_failure_of_that_slot():
    incomplete = {k: v for k, v in GOOD.items() if k != "plan_note"}
    copy, llm = play({**incomplete, "cover_title": 7}, GOOD)
    assert len(llm.calls) == 2
    assert [s["id"] for s in llm.calls[1][1]["slots"]] == ["cover_title", "plan_note"]
    assert copy == GOOD


def test_the_second_call_sends_only_the_failing_slots_with_the_reason_for_each_and_the_rest_unchanged():
    _, llm = play({**GOOD, "cover_title": TOO_LONG, "plan_note": ""}, GOOD)
    first, second = llm.calls[0][1], llm.calls[1][1]
    assert "problems" not in first
    assert [s["id"] for s in second["slots"]] == ["cover_title", "plan_note"]
    assert set(second["problems"]) == {"cover_title", "plan_note"}
    assert "41" in second["problems"]["cover_title"] and "40" in second["problems"]["cover_title"]
    assert "empty" in second["problems"]["plan_note"]
    assert {k: v for k, v in second.items() if k not in ("slots", "problems")} == {k: v for k, v in first.items() if k != "slots"}


def test_slots_that_passed_the_first_time_are_kept_whatever_the_second_reply_says_about_them():
    second = {**GOOD, "cover_title": "Aurelia Heights, Pune", "plan_note": "REWRITTEN", "about_headline": "x" * 500}
    copy, _ = play({**GOOD, "cover_title": TOO_LONG}, second)
    assert copy["cover_title"] == "Aurelia Heights, Pune"
    assert copy["plan_note"] == GOOD["plan_note"]
    assert copy["about_headline"] == GOOD["about_headline"]


def test_a_second_reply_that_fixes_one_slot_and_not_the_other_keeps_the_fixed_one():
    copy, llm = play({**GOOD, "cover_title": TOO_LONG, "plan_note": ""}, {**GOOD, "plan_note": ""})
    assert len(llm.calls) == 2
    assert copy["cover_title"] == GOOD["cover_title"]
    assert "plan_note" not in copy


# --- a slot that still fails is left out, with one warning --------------------------------------------------------------

def warnings(caplog) -> list[str]:
    return [r.getMessage() for r in caplog.records if r.levelno >= logging.WARNING]


def test_a_slot_that_fails_twice_is_left_out_and_exactly_one_warning_says_which_and_why(caplog):
    bad = {**GOOD, "cover_title": TOO_LONG}
    copy, llm = play(bad, bad)
    assert len(llm.calls) == 2  # asked once more, not again
    assert set(copy) == set(OWNED) - {"cover_title"}
    (message,) = warnings(caplog)
    assert "cover_title" in message and "41 characters, the limit is 40" in message


def test_several_slots_that_fail_twice_share_one_warning(caplog):
    bad = {**GOOD, "cover_title": TOO_LONG, "plan_note": "", "about_headline": "Near Zorbaville"}
    copy, _ = play(bad, bad)
    assert set(copy) == set(OWNED) - {"cover_title", "plan_note", "about_headline"}
    (message,) = warnings(caplog)
    assert all(slot_id in message for slot_id in ("cover_title", "plan_note", "about_headline"))
    assert "Zorbaville" in message and "empty" in message


def test_the_reason_in_the_warning_is_the_one_from_the_second_attempt(caplog):
    play({**GOOD, "cover_title": TOO_LONG}, {**GOOD, "cover_title": "Heights in Zorbaville"})
    (message,) = warnings(caplog)
    assert "Zorbaville" in message and "41 characters" not in message


def test_no_warning_when_every_slot_passes(caplog):
    caplog.set_level(logging.INFO, logger="brochure.agents.copywriter")
    play(GOOD)
    assert warnings(caplog) == []


# --- the client fails: the run never crashes ---------------------------------------------------------------------------

@pytest.mark.parametrize("error", [
    LLMRateLimited("rate limit still hit after 3 attempts"),
    LLMBadReply("the model's reply is not valid JSON"),
    LLMError("HTTP 500 from the provider"),
])
def test_a_client_error_on_the_first_call_gives_no_copy_and_one_warning_without_raising(error, caplog):
    copy, llm = play(error)
    assert copy == {}
    assert len(llm.calls) == 1
    (message,) = warnings(caplog)
    assert str(error) in message
    assert all(slot_id in message for slot_id in OWNED)


def test_a_client_error_on_the_second_call_keeps_the_slots_that_passed_and_one_warning_names_the_rest(caplog):
    copy, llm = play({**GOOD, "cover_title": TOO_LONG}, LLMRateLimited("rate limit"))
    assert copy == {k: v for k, v in GOOD.items() if k != "cover_title"}
    (message,) = warnings(caplog)
    assert "cover_title" in message and "41 characters" in message and "rate limit" in message
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
    _, llm = play({**GOOD, "cover_title": TOO_LONG}, GOOD, qa_issues=[qa_issue("copywriter", note="tone")])
    assert llm.calls[1][1]["qa_issues"] == llm.calls[0][1]["qa_issues"]


# --- each kind of check is wired in ------------------------------------------------------------------------------------

@pytest.mark.parametrize("bad, reason", [
    ("Homes of 900 sq ft", "900"),                       # a number the facts do not have
    ("Five minutes from the metro", "Five"),             # a number word the facts do not have
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
    copy, _ = play({**GOOD, "cover_title": "Aurelia\u202fHeights"})
    assert copy["cover_title"] == "Aurelia Heights" and len(copy["cover_title"]) <= OWNED["cover_title"]


def test_the_prompt_says_each_highlight_line_states_a_fact_from_the_project_not_a_picture():
    prompt = PROMPT_FILE.read_text(encoding="utf-8")
    rule = next(line for line in prompt.splitlines() if "overview_highlights" in line and line[0].isdigit())
    for word in ("fact", "configuration", "location", "possession", "amenity", "landmark", "picture"):
        assert word in rule
