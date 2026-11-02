"""The checks on one slot of copy: facts are strict, wording is free. Each check gives short readable reasons."""
import re
from dataclasses import dataclass

from brochure.contracts.project import ProjectFacts

NUMBER_WORDS = {
    word: value
    for value, word in enumerate(
        "one two three four five six seven eight nine ten eleven twelve thirteen fourteen fifteen sixteen seventeen "
        "eighteen nineteen twenty".split(),
        start=1,
    )
}
_NUMBER = re.compile(r"\d{1,3}(?:,\d{3})+(?:\.\d+)?|\d+(?:\.\d+)?")  # a comma only counts inside 1,090
_NUMBER_WORD = re.compile(r"\b(" + "|".join(NUMBER_WORDS) + r")\b", re.IGNORECASE)


@dataclass(frozen=True)
class Known:
    """What the copy may mention: the numbers and the words found in the project facts and the company name."""

    numbers: frozenset[float]
    words: frozenset[str]


def _numbers_in(text: str) -> list[tuple[str, float]]:
    """(as written, value) for every number in the text, digits and number words alike, in reading order."""
    found = [(m.start(), m.group(), float(m.group().replace(",", ""))) for m in _NUMBER.finditer(text)]
    found += [(m.start(), m.group(), float(NUMBER_WORDS[m.group().lower()])) for m in _NUMBER_WORD.finditer(text)]
    return [(written, value) for _, written, value in sorted(found)]


def _strings_and_numbers(value):
    if isinstance(value, bool):
        return
    if isinstance(value, (str, int, float)):
        yield value
    elif isinstance(value, dict):
        for item in value.values():
            yield from _strings_and_numbers(item)
    elif isinstance(value, list):
        for item in value:
            yield from _strings_and_numbers(item)


def known_from(facts: ProjectFacts, company_name: str) -> Known:
    numbers = set()
    for leaf in _strings_and_numbers(facts.model_dump()):
        if isinstance(leaf, str):
            numbers.update(value for _, value in _numbers_in(leaf))
        else:
            numbers.add(float(leaf))
    return Known(frozenset(numbers), frozenset())


def _unknown_numbers(text: str, known: Known) -> list[str]:
    unknown = {}
    for written, value in _numbers_in(text):
        if value not in known.numbers:
            unknown.setdefault(written, None)
    return list(unknown)


def problems(text: str, char_budget: int, known: Known) -> list[str]:
    """Why this text cannot be used for a slot with this budget; empty when it can."""
    if not text.strip():
        return ["the text is empty"]
    reasons = []
    if len(text) > char_budget:
        reasons.append(f"{len(text)} characters, the limit is {char_budget}")
    if unknown := _unknown_numbers(text, known):
        reasons.append(f"not in the project facts: number {', '.join(unknown)}")
    return reasons
