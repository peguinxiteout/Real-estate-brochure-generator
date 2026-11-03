"""The filler the full-budget test renders: exact length, realistic words and lines."""
import pytest

from tests.support import filler_text


@pytest.mark.parametrize("chars", [1, 2, 15, 40, 60, 599, 600, 1000])
def test_running_filler_has_exactly_the_length_asked_for_and_no_space_at_its_ends(chars):
    text = filler_text(chars)
    assert len(text) == chars and text == text.strip() and "\n" not in text


@pytest.mark.parametrize("chars, line", [(400, 29), (300, 16), (400, 23), (240, 30), (31, 15), (32, 15), (33, 15)])
def test_lined_filler_counts_its_newlines_and_every_line_has_text(chars, line):
    text = filler_text(chars, line)
    lines = text.split("\n")
    assert len(text) == chars
    assert all(ln.strip() and ln == ln.strip() for ln in lines)
    assert all(len(ln) == line for ln in lines[:-1]) and len(lines[-1]) <= line + 1


def test_a_label_starts_each_line_and_is_counted():
    text = filler_text(700, 49, label="Flooring: ")
    assert len(text) == 700
    assert all(ln.startswith("Flooring: ") for ln in text.split("\n"))


def test_the_lines_are_not_all_the_same_words():
    assert len(set(filler_text(400, 29).split("\n"))) > 5
