"""Tests for ``summarizer.fill_prompt``.

Pure-helper coverage per plan.md Phase 0 Decision 7.
"""

from __future__ import annotations

import logging

import pytest

from summarizer import fill_prompt


def test_fill_prompt_substitutes_all_known_placeholders() -> None:
    template = "chat={{chat_name}}; messages={{messages}}; summaries={{summaries}}"

    rendered_output = fill_prompt(
        template,
        chat_name="General",
        messages="line 1\nline 2",
        summaries="- topic one\n- topic two",
    )

    assert rendered_output == (
        "chat=General; messages=line 1\nline 2; summaries=- topic one\n- topic two"
    )


def test_fill_prompt_leaves_unresolved_token_in_place_and_warns(
    caplog: pytest.LogCaptureFixture,
) -> None:
    template = "chat={{chat_name}}; unknown={{unknown_token}}"

    with caplog.at_level(logging.WARNING, logger="summarizer"):
        rendered_output = fill_prompt(template, chat_name="General")

    assert rendered_output == "chat=General; unknown={{unknown_token}}"
    warning_records = [
        record for record in caplog.records if record.levelno == logging.WARNING
    ]
    assert len(warning_records) == 1
    assert "{{unknown_token}}" in warning_records[0].getMessage()


def test_fill_prompt_does_not_raise_when_token_is_unresolved() -> None:
    template = "something={{missing}}"

    rendered_output = fill_prompt(template)

    assert rendered_output == "something={{missing}}"
