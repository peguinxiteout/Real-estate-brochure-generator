"""The checks on one slot of copy: facts are strict, wording is free. Each check gives short readable reasons."""
import re
from dataclasses import dataclass
from pathlib import Path

from brochure.contracts.project import ProjectFacts

DATA_DIR = Path(__file__).parent / "data"

NUMBER_WORDS = {
    word: value
    for value, word in enumerate(
        "one two three four five six seven eight nine ten eleven twelve thirteen fourteen fifteen sixteen seventeen "
        "eighteen nineteen twenty".split(),
        start=1,
    )
}
_NUMBER = re.compile(r"\d{1,3}(?:,\d{3})+(?:\.\d+)?|\d+(?:\.\d+)?")  # a comma only counts inside 1,090
_WORD = re.compile(r"[^\W\d_]+(?:['’][^\W\d_]+)*")  # letters, with an inner apostrophe: Children's
_SKIPPED_BEFORE_A_WORD = " \t\"'“‘([*•–—-"  # quotes, brackets and bullets in front of a sentence's first word
_NUMBER_WORD = re.compile(r"\b(" + "|".join(NUMBER_WORDS) + r")\b", re.IGNORECASE)


@dataclass(frozen=True)
class Known:
    """What the copy may mention: the numbers and the words found in the project facts and the company name."""

    numbers: frozenset[float]
    words: frozenset[str]


def _data_lines(name: str) -> list[str]:
    """The entries of a data file: one per line, blank lines and # comments skipped."""
    lines = (DATA_DIR / name).read_text(encoding="utf-8").splitlines()
    return [line.strip() for line in lines if line.strip() and not line.lstrip().startswith("#")]


def _phrase_pattern(entry: str) -> re.Pattern:
    """A whole-word, case-insensitive pattern for a word or phrase; spaces in a phrase match any run of spaces."""
    start = r"(?<!\w)" if re.match(r"\w", entry) else ""  # an entry such as the rupee sign has no word edge
    end = r"(?!\w)" if re.search(r"\w$", entry) else ""
    return re.compile(start + r"\s+".join(re.escape(part) for part in entry.split()) + end, re.IGNORECASE)


def _listed_in(text: str, data_file: str) -> list[str]:
    """The entries of the data file that the text contains."""
    return [entry for entry in _data_lines(data_file) if _phrase_pattern(entry).search(text)]


def _name_key(word: str) -> str:
    """A word as compared: lower case, without a possessive ('s)."""
    word = word.casefold()
    return word[:-2] if word.endswith(("'s", "’s")) else word


def _words_in(text: str) -> list[tuple[str, bool]]:
    """(word, starts a sentence or line) for every word in the text."""
    words = []
    for match in _WORD.finditer(text):
        before = text[: match.start()].rstrip(_SKIPPED_BEFORE_A_WORD)
        words.append((match.group(), before == "" or before.endswith(("\n", ".", "!", "?"))))
    return words


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
    numbers, words = set(), {_name_key(w) for w in _data_lines("copy_name_allowlist.txt")}
    for leaf in [*_strings_and_numbers(facts.model_dump()), company_name]:
        if isinstance(leaf, str):
            numbers.update(value for _, value in _numbers_in(leaf))
            words.update(_name_key(word) for word, _ in _words_in(leaf))
        else:
            numbers.add(float(leaf))
    return Known(frozenset(numbers), frozenset(words))


def _unknown_numbers(text: str, known: Known) -> list[str]:
    unknown = {}
    for written, value in _numbers_in(text):
        if value not in known.numbers:
            unknown.setdefault(written, None)
    return list(unknown)


def _unknown_names(text: str, known: Known) -> list[str]:
    """Capitalised words that are not the first word of a sentence and that nothing in the facts accounts for."""
    unknown = {}
    for word, starts_sentence in _words_in(text):
        if word[0].isupper() and not starts_sentence and _name_key(word) not in known.words:
            unknown.setdefault(_name_key(word), word)
    return list(unknown.values())


def problems(text: str, char_budget: int, known: Known) -> list[str]:
    """Why this text cannot be used for a slot with this budget; empty when it can."""
    if not text.strip():
        return ["the text is empty"]
    reasons = []
    if len(text) > char_budget:
        reasons.append(f"{len(text)} characters, the limit is {char_budget}")
    if unknown := _unknown_numbers(text, known):
        reasons.append(f"not in the project facts: number {', '.join(unknown)}")
    if unknown := _unknown_names(text, known):
        reasons.append(f"not in the project facts: name {', '.join(unknown)}")
    if money := _listed_in(text, "copy_money_words.txt"):
        reasons.append(f"money or investment wording: {', '.join(money)}")
    if banned := _listed_in(text, "copy_banned_phrases.txt"):
        reasons.append(f"superlative or promise: {', '.join(banned)}")
    return reasons
