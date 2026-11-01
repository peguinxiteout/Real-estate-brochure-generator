"""sample/brief_sparse.json: the Aurelia Heights brief with a form that leaves out what the prompt states in words."""
import json
from pathlib import Path

from brochure.contracts.project import Brief
from brochure.pipeline.brief import missing_fields

SAMPLE = Path(__file__).parents[2] / "sample"


def sparse() -> Brief:
    return Brief.model_validate(json.loads((SAMPLE / "brief_sparse.json").read_text(encoding="utf-8")))


def test_the_sparse_brief_validates_and_is_the_same_project_as_the_full_one():
    full = Brief.model_validate(json.loads((SAMPLE / "brief.json").read_text(encoding="utf-8")))
    assert sparse().form.name == full.form.name
    assert sparse().form.rera_state == full.form.rera_state


def test_the_form_leaves_out_fields_the_prompt_states_in_plain_words():
    brief = sparse()
    assert brief.form.rera_number is None
    assert brief.form.possession is None
    assert brief.form.configurations == []
    assert brief.form.tone_notes == ""
    for stated in ["P99999000000 (SAMPLE)", "2 BHK", "780", "3 BHK", "1090", "December 2028", "warm and aspirational"]:
        assert stated in brief.prompt


def test_one_field_is_missing_from_the_form_and_not_mentioned_in_the_prompt_at_all():
    brief = sparse()
    assert brief.form.location is None
    for hint in ["Meridian Park", "Pune", "Road"]:
        assert hint not in brief.prompt
    assert "location" in missing_fields(brief.form)
