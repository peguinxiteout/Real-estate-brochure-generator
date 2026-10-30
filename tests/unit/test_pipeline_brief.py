"""The brief step turns the form into ProjectFacts, or says which fields it still needs."""
import pytest

from brochure.contracts.project import ProjectFacts
from brochure.llm import FakeLLM
from brochure.pipeline.brief import brief_step
from tests.support import sample_state


@pytest.fixture
def llm():
    return FakeLLM({})


def test_a_complete_form_becomes_project_facts_with_nothing_missing(llm):
    state = sample_state(briefed=False)
    outcome = brief_step(state, llm)
    assert outcome.missing_fields == []
    assert outcome.project_facts == ProjectFacts.model_validate(state.brief.form.model_dump())
    assert outcome.project_facts.name == "Aurelia Heights"
    assert llm.calls == []


def test_a_form_without_rera_number_gives_no_facts_and_names_the_missing_field(llm):
    outcome = brief_step(sample_state(briefed=False, rera_number=None), llm)
    assert outcome.project_facts is None
    assert outcome.missing_fields == ["rera_number"]


def test_a_blank_rera_number_counts_as_missing(llm):
    assert brief_step(sample_state(briefed=False, rera_number="  "), llm).missing_fields == ["rera_number"]


def test_every_missing_field_is_listed_in_the_order_of_the_form(llm):
    outcome = brief_step(sample_state(briefed=False, possession=None, name=None, rera_number=None), llm)
    assert outcome.missing_fields == ["name", "rera_number", "possession"]
