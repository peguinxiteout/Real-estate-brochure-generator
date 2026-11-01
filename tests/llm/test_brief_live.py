"""The Brief agent against the real model. Run by hand with a key; CI never runs it (marker `llm`).

It asserts properties only: the model's wording differs from run to run, what it may not do does not.
"""
import json
import re
from pathlib import Path

import pytest

from brochure.agents.brief import brief_agent
from brochure.contracts.project import Brief, BriefForm

pytestmark = pytest.mark.llm

SAMPLE = Path(__file__).parents[2] / "sample"


def squash(text: str) -> str:
    return " ".join(text.split()).casefold()


def numbers(text: str) -> set[float]:
    return {float(n.replace(",", "")) for n in re.findall(r"\d[\d,]*(?:\.\d+)?", text)}


def new_values(before: BriefForm, after: BriefForm) -> dict[str, object]:
    """The fields the agent filled."""
    return {f: getattr(after, f) for f in BriefForm.model_fields if getattr(after, f) != getattr(before, f)}


def test_the_real_model_fills_the_sparse_form_with_grounded_values_only(live_llm):
    brief = Brief.model_validate(json.loads((SAMPLE / "brief_sparse.json").read_text(encoding="utf-8")))
    form = brief_agent(brief, live_llm)

    BriefForm.model_validate(form.model_dump())  # a valid form
    filled = new_values(brief.form, form)
    assert filled, "the model filled nothing: it failed (see the log) or returned only nulls"

    text, known = squash(brief.prompt), numbers(brief.prompt)
    for field, value in filled.items():
        for leaf in strings_and_numbers(value):
            if isinstance(leaf, str):
                assert squash(leaf) in text, f"{field}: {leaf!r} is not in the prompt"
            else:
                assert leaf in known, f"{field}: {leaf!r} is not in the prompt"

    assert form.rera_number is None or form.rera_number in brief.prompt  # never invented
    assert brief.form.location is None and form.location is None  # the prompt never mentions it


def strings_and_numbers(value):
    """Every string and number inside a filled value (a string, or a list of strings or models)."""
    if isinstance(value, (str, int, float)):
        yield value
    elif isinstance(value, list):
        for item in value:
            yield from strings_and_numbers(item)
    elif hasattr(value, "model_dump"):
        yield from strings_and_numbers(list(value.model_dump().values()))
