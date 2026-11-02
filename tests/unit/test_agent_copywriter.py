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
