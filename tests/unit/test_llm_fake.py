from pathlib import Path

import pytest

from brochure.llm import FakeLLM, LLMClient


def test_returns_the_canned_response_for_the_task():
    llm = FakeLLM({"brief.extract": {"name": "Aurelia Heights"}, "copy.write": {"title": "Live above it all"}})
    assert llm.complete("brief.extract", {"prompt": "x"}) == {"name": "Aurelia Heights"}
    assert llm.complete("copy.write", {}) == {"title": "Live above it all"}


def test_records_every_call_with_task_payload_and_images():
    llm = FakeLLM({"vision.tag": {"kind": "photo"}})
    llm.complete("vision.tag", {"path": "a.jpg"}, images=[Path("a.jpg")])
    llm.complete("vision.tag", {"path": "b.jpg"})
    assert [(c.task, c.payload, c.images) for c in llm.calls] == [
        ("vision.tag", {"path": "a.jpg"}, [Path("a.jpg")]),
        ("vision.tag", {"path": "b.jpg"}, []),
    ]
