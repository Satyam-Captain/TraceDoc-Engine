"""Tests for deterministic sentence splitting."""

from __future__ import annotations

from app.evidence.sentence_splitter import split_sentences


def test_split_two_sentences_on_period() -> None:
    text = "The most common architecture is X. A second architecture is Y."
    sentences = split_sentences(text)

    assert len(sentences) == 2
    assert sentences[0] == "The most common architecture is X."
    assert sentences[1] == "A second architecture is Y."


def test_split_preserves_abbreviation_periods() -> None:
    text = "See e.g. repository connectors. A third architecture is Z."
    sentences = split_sentences(text)

    assert len(sentences) == 2
    assert "e.g." in sentences[0]
    assert sentences[1].startswith("A third architecture")


def test_split_skips_empty_segments() -> None:
    assert split_sentences("   \n\n  ") == []
