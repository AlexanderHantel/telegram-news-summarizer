"""Tests für den Markdown-zu-Telegram-HTML-Konverter."""

from __future__ import annotations

from markdown_zu_html import konvertiere_markdown_zu_telegram_html


def test_konvertiert_fett_zu_b_tag() -> None:
    assert konvertiere_markdown_zu_telegram_html("**Тема**") == "<b>Тема</b>"


def test_konvertiert_link_zu_a_tag() -> None:
    eingabe = "[Klick mich](https://example.com)"
    erwartet = '<a href="https://example.com">Klick mich</a>'
    assert konvertiere_markdown_zu_telegram_html(eingabe) == erwartet


def test_escaped_html_sonderzeichen_in_text() -> None:
    eingabe = "1 < 2 & 3 > 0"
    erwartet = "1 &lt; 2 &amp; 3 &gt; 0"
    assert konvertiere_markdown_zu_telegram_html(eingabe) == erwartet


def test_escaped_anführungszeichen_in_url() -> None:
    eingabe = '[t](https://x.com/"path")'
    erwartet = '<a href="https://x.com/&quot;path&quot;">t</a>'
    assert konvertiere_markdown_zu_telegram_html(eingabe) == erwartet


def test_link_text_darf_fett_enthalten() -> None:
    eingabe = "[**Wichtig**](https://example.com)"
    erwartet = '<a href="https://example.com"><b>Wichtig</b></a>'
    assert konvertiere_markdown_zu_telegram_html(eingabe) == erwartet


def test_emoji_bleibt_unverändert() -> None:
    eingabe = "🔸 Тест 🔸"
    assert konvertiere_markdown_zu_telegram_html(eingabe) == "🔸 Тест 🔸"


def test_klartext_ohne_marker_bleibt_unverändert() -> None:
    eingabe = "Простой русский текст без разметки."
    assert konvertiere_markdown_zu_telegram_html(eingabe) == eingabe


def test_unbalancierte_sterne_bleiben_klartext() -> None:
    eingabe = "**unfertig"
    assert konvertiere_markdown_zu_telegram_html(eingabe) == "**unfertig"


def test_amp_in_url_wird_zu_amp_entity() -> None:
    eingabe = "[Suche](https://example.com/?q=1&page=2)"
    erwartet = '<a href="https://example.com/?q=1&amp;page=2">Suche</a>'
    assert konvertiere_markdown_zu_telegram_html(eingabe) == erwartet


def test_script_tag_in_text_wird_neutralisiert() -> None:
    eingabe = "<script>alert(1)</script>"
    erwartet = "&lt;script&gt;alert(1)&lt;/script&gt;"
    assert konvertiere_markdown_zu_telegram_html(eingabe) == erwartet


def test_russischer_beispieltext_komplett() -> None:
    eingabe = (
        '**Сводка чата "Имя" за 05.05.2026**\n\n'
        "🔸 **Тема**: Текст с **выделением** и [ссылкой](https://x.com).\n"
    )
    erwartet = (
        '<b>Сводка чата "Имя" за 05.05.2026</b>\n\n'
        "🔸 <b>Тема</b>: Текст с <b>выделением</b> и "
        '<a href="https://x.com">ссылкой</a>.\n'
    )
    assert konvertiere_markdown_zu_telegram_html(eingabe) == erwartet


def test_mehrere_fett_paare_in_einer_zeile() -> None:
    eingabe = "**A** und **B**"
    erwartet = "<b>A</b> und <b>B</b>"
    assert konvertiere_markdown_zu_telegram_html(eingabe) == erwartet


def test_leerstring_bleibt_leer() -> None:
    assert konvertiere_markdown_zu_telegram_html("") == ""
