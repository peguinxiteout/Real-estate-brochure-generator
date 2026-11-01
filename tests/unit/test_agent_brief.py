"""The Brief agent with a FakeLLM: what it fills, what it refuses to fill, and how it fails. No network."""
import json
from pathlib import Path

import pytest

from brochure.agents.brief import brief_agent
from brochure.contracts.project import Brief, BriefForm
from brochure.llm import FakeLLM

SAMPLE = Path(__file__).parents[2] / "sample"


def sparse() -> Brief:
    return Brief.model_validate(json.loads((SAMPLE / "brief_sparse.json").read_text(encoding="utf-8")))


def reply(**fields) -> dict:
    """A model reply in the full shape: every key present, nothing extracted unless given."""
    empty = {
        "name": None, "rera_number": None, "rera_state": None, "location": None, "configurations": [],
        "amenities": [], "specifications": [], "landmarks": [], "possession": None, "tone_notes": None,
    }
    return {**empty, **fields}


# What the model should find in sample/brief_sparse.json's prompt.
STATED = reply(
    rera_number="P99999000000 (SAMPLE)",
    configurations=[{"label": "2 BHK", "carpet_area_sqft": 780}, {"label": "3 BHK", "carpet_area_sqft": 1090}],
    possession="December 2028",
    tone_notes="warm and aspirational, calm and confident",
)


def run(canned: dict, brief: Brief | None = None) -> tuple[BriefForm, FakeLLM]:
    llm = FakeLLM({"brief.extract": canned})
    return brief_agent(brief or sparse(), llm), llm


def test_empty_form_fields_are_filled_from_what_the_model_found_in_the_prompt():
    form, _ = run(STATED)
    assert form.rera_number == "P99999000000 (SAMPLE)"
    assert form.possession == "December 2028"
    assert [(c.label, c.carpet_area_sqft) for c in form.configurations] == [("2 BHK", 780), ("3 BHK", 1090)]
    assert form.tone_notes == "warm and aspirational, calm and confident"
    assert form.location is None  # the prompt does not say, so it stays empty


def test_a_filled_form_field_is_never_overwritten_by_the_model():
    brief = sparse()
    brief = brief.model_copy(update={"form": brief.form.model_copy(update={"possession": "Dec 2027", "tone_notes": "Plain."})})
    form, _ = run(STATED, brief)
    assert form.possession == "Dec 2027"
    assert form.tone_notes == "Plain."
    assert form.name == "Aurelia Heights"
    assert form.rera_number == "P99999000000 (SAMPLE)"  # still empty in the form, so still filled
