"""The Copywriter against the real model. Run by hand with a key; CI never runs it (marker `llm`).

The wording differs from run to run;
what it must satisfy does not: every owned slot filled, every code check passing, no fallback, one or two calls. It prints each slot and the call count.
"""
import json
import logging
from pathlib import Path

import pytest

from brochure.agents.copy_checks import known_from, problems
from brochure.agents.copywriter import CopyInputs, copywriter_agent, owned_slots
from brochure.contracts.images import ImageTag
from brochure.pipeline import load_sample_data
from tests.support import sample_state

pytestmark = pytest.mark.llm

SAMPLE = Path(__file__).parents[2] / "sample"


class CountingClient:
    """Wraps the real client and records every call (task names only; the key is never touched)."""

    def __init__(self, client):
        self.client, self.tasks = client, []

    def complete(self, task, payload, images=None):
        self.tasks.append(task)
        return self.client.complete(task, payload, images)


def test_the_real_model_writes_every_owned_slot_and_every_check_passes(live_llm, caplog, capsys):
    state = sample_state()  # sample/brief.json: the complete form
    tags = [ImageTag.model_validate(t) for t in json.loads((SAMPLE / "image_tags.json").read_text(encoding="utf-8"))]
    slots = owned_slots(load_sample_data().template)
    inputs = CopyInputs(state.project_facts, state.brand_kit.company_name, tags, slots)
    client = CountingClient(live_llm)
    caplog.set_level(logging.INFO, logger="brochure.agents.copywriter")

    copy = copywriter_agent(inputs, client)

    with capsys.disabled():  # shown without -s; slot ids, the copy and a count, never the key
        print(f"\nCopywriter: {len(client.tasks)} call(s) to the model {client.tasks}")
        for slot in slots:
            text = copy.get(slot.id)
            shown = "(missing)" if text is None else f"[{len(text)}/{slot.char_budget}] {text!r}"
            print(f"  {slot.id}: {shown}")

    # the model was called, once or twice, and the agent did not fall back
    assert client.tasks and set(client.tasks) == {"copy.write"} and len(client.tasks) <= 2, client.tasks
    fallbacks = [r.getMessage() for r in caplog.records if r.levelno >= logging.WARNING]
    assert not fallbacks, f"the Copywriter left slots without copy: {fallbacks}"

    # every owned slot is filled, and every text passes the same checks again
    assert set(copy) == {s.id for s in slots}
    known = known_from(state.project_facts, state.brand_kit.company_name)
    for slot in slots:
        assert problems(copy[slot.id], slot.char_budget, known) == [], f"{slot.id}: {copy[slot.id]!r}"
