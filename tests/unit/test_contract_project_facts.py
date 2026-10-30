import pytest
from pydantic import ValidationError

from brochure.contracts.project import Brief, BriefForm, ProjectFacts


def facts_data(**overrides):
    data = {
        "name": "Aurelia Heights",
        "rera_number": "P99999000000",
        "rera_state": "Maharashtra",
        "location": "Baner, Pune",
        "configurations": [
            {"label": "2 BHK", "carpet_area_sqft": 780},
            {"label": "3 BHK", "carpet_area_sqft": 1090},
        ],
        "amenities": ["Infinity pool", "Clubhouse"],
        "specifications": [{"category": "Flooring", "detail": "Vitrified tiles"}],
        "landmarks": [{"name": "Baner Road", "distance_km": 1.2}],
        "possession": "Dec 2028",
        "tone_notes": "Warm, aspirational, no hype",
    }
    data.update(overrides)
    return data


def test_valid_project_facts_parse():
    facts = ProjectFacts.model_validate(facts_data())
    assert facts.rera_number == "P99999000000"
    assert facts.configurations[1].carpet_area_sqft == 1090
    assert facts.landmarks[0].distance_km == 1.2
    assert facts.specifications[0].category == "Flooring"


@pytest.mark.parametrize("blank", ["", "   "])
def test_blank_rera_number_is_rejected(blank):
    with pytest.raises(ValidationError):
        ProjectFacts.model_validate(facts_data(rera_number=blank))


@pytest.mark.parametrize("area", [0, -10])
def test_configuration_carpet_area_must_be_positive(area):
    bad = [{"label": "2 BHK", "carpet_area_sqft": area}]
    with pytest.raises(ValidationError):
        ProjectFacts.model_validate(facts_data(configurations=bad))


def test_brief_is_a_form_plus_a_short_prompt():
    brief = Brief.model_validate(
        {"form": facts_data(), "prompt": "Premium 2 and 3 BHK homes for upper-middle-class families."}
    )
    assert brief.form.name == "Aurelia Heights"
    assert brief.prompt.startswith("Premium")


def test_brief_form_accepts_a_partly_filled_form_with_empty_lists_by_default():
    form = BriefForm.model_validate({"name": "Aurelia Heights", "possession": "Dec 2028"})
    assert form.name == "Aurelia Heights"
    assert form.rera_number is None
    assert (form.configurations, form.amenities, form.specifications, form.landmarks) == ([], [], [], [])


def test_an_empty_brief_form_is_valid():
    assert BriefForm().name is None


def test_brief_form_rejects_unknown_fields():
    with pytest.raises(ValidationError, match="Extra inputs"):
        BriefForm.model_validate({"nmae": "typo"})


def test_a_complete_brief_form_converts_to_project_facts_unchanged():
    form = BriefForm.model_validate(facts_data())
    assert ProjectFacts.model_validate(form.model_dump()) == ProjectFacts.model_validate(facts_data())


def test_a_form_without_rera_number_is_valid_but_cannot_become_project_facts():
    data = facts_data()
    del data["rera_number"]
    form = BriefForm.model_validate(data)
    assert form.rera_number is None
    with pytest.raises(ValidationError, match="rera_number"):
        ProjectFacts.model_validate(form.model_dump())


def test_tone_notes_are_optional_all_the_way_through_conversion():
    data = facts_data()
    del data["tone_notes"]
    facts = ProjectFacts.model_validate(BriefForm.model_validate(data).model_dump())
    assert facts.tone_notes == ""
