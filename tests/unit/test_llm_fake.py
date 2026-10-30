from pathlib import Path

import pytest

from brochure.llm import FakeLLM, LLMClient


def test_returns_the_canned_response_for_the_task():
    llm = FakeLLM({"brief.extract": {"name": "Aurelia Heights"}, "copy.write": {"title": "Live above it all"}})
    assert llm.complete("brief.extract", {"prompt": "x"}) == {"name": "Aurelia Heights"}
    assert llm.complete("copy.write", {}) == {"title": "Live above it all"}
