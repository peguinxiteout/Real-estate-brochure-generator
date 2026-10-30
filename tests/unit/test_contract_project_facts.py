import pytest
from pydantic import ValidationError

from brochure.contracts.project import ProjectFacts


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
