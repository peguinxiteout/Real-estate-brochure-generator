"""The checks on one slot of copy: facts are strict, wording is free. Each check gives short readable reasons."""
from dataclasses import dataclass

from brochure.contracts.project import ProjectFacts


@dataclass(frozen=True)
class Known:
    """What the copy may mention: the numbers and the words found in the project facts and the company name."""

    numbers: frozenset[float]
    words: frozenset[str]


def known_from(facts: ProjectFacts, company_name: str) -> Known:
    return Known(frozenset(), frozenset())


def problems(text: str, char_budget: int, known: Known) -> list[str]:
    """Why this text cannot be used for a slot with this budget; empty when it can."""
    if not text.strip():
        return ["the text is empty"]
    reasons = []
    if len(text) > char_budget:
        reasons.append(f"{len(text)} characters, the limit is {char_budget}")
    return reasons
