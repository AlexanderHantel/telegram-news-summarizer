"""Tests for the ``bot_sender`` chunker.

Verifies the verbatim-concatenation contract from FR-018 / SC-006.
"""

from __future__ import annotations

from bot_sender import _TELEGRAM_MAX_MESSAGE_LENGTH, _split_into_delivery_chunks


def test_chunker_returns_single_chunk_for_short_text() -> None:
    short_text = "hello"

    chunks = _split_into_delivery_chunks(short_text)

    assert chunks == ["hello"]
    assert "".join(chunks) == short_text


def test_chunker_preserves_verbatim_concatenation_for_multi_paragraph_text() -> None:
    long_paragraph_text = "\n\n".join(
        [("A" * 2000) for _ in range(4)]
    )

    chunks = _split_into_delivery_chunks(long_paragraph_text)

    assert "".join(chunks) == long_paragraph_text
    assert all(len(chunk) <= _TELEGRAM_MAX_MESSAGE_LENGTH for chunk in chunks)
    assert len(chunks) >= 2


def test_chunker_prefers_paragraph_boundary_over_hard_split() -> None:
    first_paragraph_body = "A" * 3000
    second_paragraph_body = "B" * 3000
    composed_text = first_paragraph_body + "\n\n" + second_paragraph_body

    chunks = _split_into_delivery_chunks(composed_text)

    assert "".join(chunks) == composed_text
    assert len(chunks) == 2
    assert chunks[0] == first_paragraph_body + "\n\n"
    assert chunks[1] == second_paragraph_body


def test_chunker_hard_splits_single_paragraph_longer_than_limit() -> None:
    pathological_paragraph = "Z" * (_TELEGRAM_MAX_MESSAGE_LENGTH * 2 + 123)

    chunks = _split_into_delivery_chunks(pathological_paragraph)

    assert "".join(chunks) == pathological_paragraph
    assert all(len(chunk) <= _TELEGRAM_MAX_MESSAGE_LENGTH for chunk in chunks)
    assert len(chunks) == 3


def test_chunker_produces_no_prefix_or_suffix_markers() -> None:
    composed_text = "paragraph one\n\n" + ("Q" * 5000)

    chunks = _split_into_delivery_chunks(composed_text)

    assert "".join(chunks) == composed_text
    assert not any("Part " in chunk for chunk in chunks)
    assert not any(chunk.startswith("[") and "/" in chunk[:10] for chunk in chunks)
