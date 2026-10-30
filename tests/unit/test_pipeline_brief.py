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
