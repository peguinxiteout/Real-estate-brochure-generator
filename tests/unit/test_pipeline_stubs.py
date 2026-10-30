"""The stub agents: fixed answers from sample/, no LLM calls."""
import json

import pytest

from brochure.contracts.images import ImageTag
from brochure.llm import FakeLLM
from brochure.pipeline.stubs import stub_agents
from tests.support import ROOT, sample_state


@pytest.fixture
def llm():
    return FakeLLM({})


def test_vision_stub_returns_the_tags_of_the_12_sample_images(llm):
    tags = stub_agents().vision(sample_state(), llm)
    expected = [ImageTag.model_validate(t) for t in json.loads((ROOT / "sample" / "image_tags.json").read_text(encoding="utf-8"))]
    assert len(tags) == 12
    assert tags == expected
    assert llm.calls == []
