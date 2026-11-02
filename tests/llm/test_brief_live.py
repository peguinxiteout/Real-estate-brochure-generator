"""The Brief agent against the real model. Run by hand with a key; CI never runs it (marker `llm`).

It asserts properties only: the model's wording differs from run to run, what it must and may not do does not.
It cannot pass on the form-only fallback: it requires the fields the prompt states to be filled, and that the
model was called and no fallback warning was logged.
"""
import json
import logging
import re
from pathlib import Path

import pytest

from brochure.agents.brief import brief_agent
from brochure.contracts.project import Brief, BriefForm

pytestmark = pytest.mark.llm

SAMPLE = Path(__file__).parents[2] / "sample"
RERA = "P99999000000 (SAMPLE)"  # exactly as sample/brief_sparse.json's prompt writes it


class CountingClient:
    """Wraps the real client and records every call (task names only; the key is never touched)."""

    def __init__(self, client):
        self.client, self.tasks = client, []

    def complete(self, task, payload, images=None):
        self.tasks.append(task)
        return self.client.complete(task, payload, images)


def squash(text: str) -> str:
    return " ".join(text.split()).casefold()


def numbers(text: str) -> set[float]:
    return {float(n.replace(",", "")) for n in re.findall(r"\d[\d,]*(?:\.\d+)?", text)}


def new_values(before: BriefForm, after: BriefForm) -> dict[str, object]:
    """The fields the agent filled."""
    return {f: getattr(after, f) for f in BriefForm.model_fields if getattr(after, f) != getattr(before, f)}


def strings_and_numbers(value):
    """Every string and number inside a filled value (a string, or a list of strings or models)."""
    if isinstance(value, (str, int, float)):
        yield value
    elif isinstance(value, list):
        for item in value:
            yield from strings_and_numbers(item)
    elif hasattr(value, "model_dump"):
        yield from strings_and_numbers(list(value.model_dump().values()))


def test_the_real_model_fills_what_the_prompt_states_and_nothing_else(live_llm, caplog, capsys):
    brief = Brief.model_validate(json.loads((SAMPLE / "brief_sparse.json").read_text(encoding="utf-8")))
    client = CountingClient(live_llm)
    caplog.set_level(logging.INFO, logger="brochure.agents.brief")

    form = brief_agent(brief, client)

    filled = new_values(brief.form, form)
    with capsys.disabled():  # shown without -s; it holds field names and a count, never the key
        print(f"\nLLM filled: {sorted(filled)}; calls to the model: {len(client.tasks)} {client.tasks}")

    # the model was called, and the agent did not fall back to the form
    assert client.tasks and set(client.tasks) == {"brief.extract"}, "the model was never called"
    fallbacks = [r.getMessage() for r in caplog.records if r.levelno >= logging.WARNING]
    assert not fallbacks, f"the agent fell back to the form only: {fallbacks}"

    # what the prompt states is filled
    assert form.rera_number == RERA
    assert form.possession and "2028" in form.possession
    assert {(c.label, c.carpet_area_sqft) for c in form.configurations} == {("2 BHK", 780), ("3 BHK", 1090)}

    # what the prompt does not mention is still empty, and the form's own values were not touched
    assert form.location is None
    for field in ("name", "rera_state", "amenities", "specifications", "landmarks"):
        assert getattr(form, field) == getattr(brief.form, field)

    # everything filled is grounded in the prompt
    BriefForm.model_validate(form.model_dump())
    text, known = squash(brief.prompt), numbers(brief.prompt)
    for field, value in filled.items():
        for leaf in strings_and_numbers(value):
            if isinstance(leaf, str):
                assert squash(leaf) in text, f"{field}: {leaf!r} is not in the prompt"
            else:
                assert leaf in known, f"{field}: {leaf!r} is not in the prompt"
