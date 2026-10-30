import pytest
from pydantic import ValidationError

from brochure.contracts.state import PipelineState
from tests.unit.test_contract_brand_kit import brand_data
from tests.unit.test_contract_project_facts import facts_data


def state_data(**overrides):
    data = {
        "template_id": "classic-8pp",
        "brand_kit": brand_data(),
        "brief": {"form": facts_data(), "prompt": "Premium homes, warm tone."},
        "image_dir": "sample/images",
    }
    data.update(overrides)
    return data


def test_a_fresh_state_has_inputs_and_empty_working_fields():
    state = PipelineState.model_validate(state_data())
    assert state.brand_kit.company_name == "Kestrel Urbanscapes"
    assert state.brief.form.name == "Aurelia Heights"
    assert state.brief.prompt == "Premium homes, warm tone."
    assert state.project_facts is None
    assert state.missing_fields == []
    assert state.image_tags == []
    assert state.slot_copy == {}
    assert state.spec is None
    assert state.qa_issues == []
    assert state.qa_round == 0
    assert state.approval_status == "pending"


def test_qa_round_cannot_be_negative():
    with pytest.raises(ValidationError, match="greater than or equal to 0"):
        PipelineState.model_validate(state_data(qa_round=-1))


def test_approval_status_must_be_a_known_value():
    with pytest.raises(ValidationError, match="'pending'"):
        PipelineState.model_validate(state_data(approval_status="maybe"))


def test_the_brief_agent_fills_project_facts_and_lists_what_it_still_needs_to_ask():
    facts = facts_data()
    state = PipelineState.model_validate(state_data(project_facts=facts, missing_fields=["rera_number"]))
    assert state.project_facts.name == "Aurelia Heights"
    assert state.missing_fields == ["rera_number"]
