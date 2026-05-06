"""Claude-backed summarization for per-chat and overall digests.

No chunking or truncation (FR-026a); no custom retry loop on top of the
Anthropic SDK (FR-026b). Prompts live as Markdown files under ``prompts/``
so the operator can tune them without touching code (Constitution
Principle III).
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import TYPE_CHECKING

from anthropic import Anthropic

from logger import get_logger
from telegram_reader import Message, serialize_messages

if TYPE_CHECKING:
    from config import Config


_PROMPTS_DIRECTORY = Path("prompts")
_CLAUDE_MAX_OUTPUT_TOKENS = 4096
_UNRESOLVED_PLACEHOLDER_PATTERN = re.compile(r"\{\{[A-Za-z0-9_]+\}\}")


def load_prompt(filename: str) -> str:
    """Return the content of a prompt file under ``prompts/``.

    Raises :class:`FileNotFoundError` with the resolved path when missing —
    callers (main.py) decide whether a missing prompt is a per-chat failure
    or a whole-run abort (see tasks.md T022).
    """
    prompt_path = _PROMPTS_DIRECTORY / filename
    if not prompt_path.is_file():
        raise FileNotFoundError(
            f"Prompt file not found: {prompt_path.resolve()}"
        )
    return prompt_path.read_text(encoding="utf-8")


def fill_prompt(template: str, **keyword_arguments: str) -> str:
    """Replace ``{{placeholder}}`` tokens; log one warning per unresolved token.

    An unresolved ``{{token}}`` is never silently dropped — it remains in the
    output verbatim so the failure surfaces in Claude's response and in the
    warning log (FR-012).
    """
    filled_template = template
    for placeholder_name, replacement_value in keyword_arguments.items():
        filled_template = filled_template.replace(
            "{{" + placeholder_name + "}}", replacement_value
        )

    logger = get_logger("summarizer")
    for unresolved_match in _UNRESOLVED_PLACEHOLDER_PATTERN.finditer(filled_template):
        logger.warning(
            "Unresolved placeholder in prompt template: %s",
            unresolved_match.group(0),
        )
    return filled_template


def _invoke_claude(anthropic_client: Anthropic, model_id: str, prompt_text: str) -> str:
    response = anthropic_client.messages.create(
        model=model_id,
        max_tokens=_CLAUDE_MAX_OUTPUT_TOKENS,
        messages=[{"role": "user", "content": prompt_text}],
    )
    response_fragments: list[str] = []
    for content_block in response.content:
        text_value = getattr(content_block, "text", None)
        if isinstance(text_value, str):
            response_fragments.append(text_value)
    return "".join(response_fragments).strip()


def summarize_chat(
    chat_name: str,
    messages: list[Message],
    config: "Config",
) -> str:
    """Summarize a single topic-chat into Russian text via Claude."""
    logger = get_logger("summarizer")
    serialized_messages = serialize_messages(messages)
    chat_summary_template = load_prompt("chat_summary.md")
    filled_prompt = fill_prompt(
        chat_summary_template,
        chat_name=chat_name,
        messages=serialized_messages,
    )

    anthropic_client = Anthropic(api_key=config.anthropic_api_key)
    summary_text = _invoke_claude(
        anthropic_client=anthropic_client,
        model_id=config.anthropic_model,
        prompt_text=filled_prompt,
    )
    logger.info(
        "Chat summary produced for '%s': input_messages=%d response_chars=%d",
        chat_name,
        len(messages),
        len(summary_text),
    )
    return summary_text


def summarize_overall(
    chat_summaries: list[tuple[str, str]],
    overall_template: str,
    config: "Config",
) -> str:
    """Summarize the aggregate of per-chat summaries into a Russian daily digest.

    ``overall_template`` is pre-loaded by ``main.py`` (see tasks.md T015 and
    T022) so that a missing overall prompt becomes a whole-run abort rather
    than a generic per-chat failure.
    """
    logger = get_logger("summarizer")
    serialized_summaries_lines: list[str] = []
    for chat_name, chat_summary_text in chat_summaries:
        serialized_summaries_lines.append(f"## {chat_name}\n\n{chat_summary_text}")
    serialized_summaries_block = "\n\n".join(serialized_summaries_lines)

    filled_prompt = fill_prompt(
        overall_template,
        summaries=serialized_summaries_block,
    )

    anthropic_client = Anthropic(api_key=config.anthropic_api_key)
    overall_summary_text = _invoke_claude(
        anthropic_client=anthropic_client,
        model_id=config.anthropic_model,
        prompt_text=filled_prompt,
    )
    logger.info(
        "Overall summary produced: input_summaries=%d response_chars=%d",
        len(chat_summaries),
        len(overall_summary_text),
    )
    return overall_summary_text
