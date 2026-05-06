"""Markdown-Subset zu Telegram-HTML-Konverter.

Wandelt das schmale Markdown-Subset, das die LLM erzeugt
(``**fett**`` und ``[text](url)``), deterministisch in das
HTML-Format um, das Telegram mit ``parse_mode=HTML`` rendert
(``<b>...</b>`` und ``<a href="...">...</a>``).

Andere Markdown-Marker (Header, Trennlinien, Listen, einfaches
Kursiv) werden bewusst nicht unterstützt und bleiben als Klartext
stehen — so wird Prompt-Drift sichtbar, statt stillschweigend
toleriert.
"""

from __future__ import annotations

import re

_FETT_MARKDOWN_REGEX = re.compile(r"\*\*([^*]+)\*\*")
_LINK_MARKDOWN_REGEX = re.compile(r"\[([^\]]+)\]\(([^)]+)\)")


def konvertiere_markdown_zu_telegram_html(markdown_text: str) -> str:
    """Konvertiert das LLM-Markdown-Subset in Telegram-HTML.

    Reihenfolge der Schritte ist signifikant:

    1. ``&``, ``<``, ``>`` werden global zu HTML-Entities escaped, damit
       beliebiger Userinhalt (z. B. ``<script>``) niemals als Tag
       interpretiert wird.
    2. ``**fett**`` wird zu ``<b>fett</b>`` umgewandelt. Erzeugt absichtlich
       unescaped ``<b>``/``</b>``-Tags — diese sind beabsichtigte HTML-Syntax.
    3. ``[text](url)`` wird zu ``<a href="url">text</a>`` umgewandelt. Innerhalb
       der ``href``-Attribut-Werte wird ``"`` zusätzlich zu ``&quot;`` escaped,
       damit das Attribut nicht vorzeitig endet.

    Schritt 2 muss vor Schritt 3 laufen: dadurch funktionieren Konstrukte
    wie ``[**X**](url)`` korrekt zu ``<a href="url"><b>X</b></a>``.
    """
    sonderzeichen_escaped_text = _escape_html_sonderzeichen(markdown_text)
    fett_konvertierter_text = _FETT_MARKDOWN_REGEX.sub(
        r"<b>\1</b>", sonderzeichen_escaped_text
    )
    link_konvertierter_text = _LINK_MARKDOWN_REGEX.sub(
        _ersetze_markdown_link_durch_a_tag, fett_konvertierter_text
    )
    return link_konvertierter_text


def _escape_html_sonderzeichen(text: str) -> str:
    """Escaped die drei für Telegram-HTML kritischen Zeichen.

    Telegram verlangt im HTML-Modus, dass ``<``, ``>`` und ``&`` außerhalb
    von Tag-Markup als Entities geschrieben werden. ``&`` muss zuerst ersetzt
    werden, sonst würde der ``&``-Anteil von ``&lt;``/``&gt;`` doppelt
    escaped.
    """
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
    )


def _ersetze_markdown_link_durch_a_tag(treffer: re.Match[str]) -> str:
    """Baut aus einem ``[text](url)``-Treffer ein ``<a href="...">``-Tag.

    Innerhalb des ``href``-Attribut-Werts werden Anführungszeichen zu
    ``&quot;`` escaped, damit das Attribut nicht vorzeitig schließt.
    """
    link_text = treffer.group(1)
    link_url_attribut_sicher = treffer.group(2).replace('"', "&quot;")
    return f'<a href="{link_url_attribut_sicher}">{link_text}</a>'
