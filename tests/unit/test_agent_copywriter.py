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
from tests.support import qa_issue, sample_state

ROOT = Path(__file__).parents[2]
TEMPLATE = load_sample_data().template
OWNED = {
    "cover_title": 40, "cover_tagline": 90, "overview_headline": 60, "overview_intro": 600, "overview_highlights": 240,
    "amenities_blurb": 250, "plan_note": 160, "about_headline": 60,
}

# Copy that passes every check for the sample project.
GOOD = {
    "cover_title": "Aurelia Heights",
    "cover_tagline": "Light, air and green space, a short walk from the metro.",
    "overview_headline": "Homes designed around light and open space",
    "overview_intro": "Aurelia Heights is a pair of residential towers in Pune with 2 and 3 BHK homes. The towers stand around a "
    "landscaped podium garden, and the plans put living rooms and bedrooms on the sides with the most daylight. The metro "
    "station, schools and a hospital are close by, so the daily routine stays short.",
    "overview_highlights": "Two towers of 2 and 3 BHK homes\nLandscaped podium garden\nShort walk to the metro\nSchools and a hospital nearby",
    "amenities_blurb": "From the infinity pool to the co-working lounge, every amenity is planned for daily use rather than for show.",
    "plan_note": "Areas shown are carpet areas. Furniture in the plans is indicative only.",
    "about_headline": "About Kestrel Urbanscapes",
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


def test_the_payload_carries_each_images_subject_and_features_and_nothing_else_no_paths():
    _, llm = run()
    images = first_payload(llm)["images"]
    assert len(images) == 12
    assert all(set(i) == {"subject", "features"} for i in images)
    assert images[0] == {"subject": "Twin residential towers at dusk, seen from the podium garden",
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
