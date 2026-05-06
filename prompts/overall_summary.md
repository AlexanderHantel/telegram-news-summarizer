# Daily overall summary

You already produced per-chat summaries of a private Telegram group for a
single operator. Below is the concatenation of those Russian per-chat
summaries.

{{summaries}}

## Your task

Write a short overall daily summary **in Russian** with **3 to 5 key
takeaways** that capture the most important signal across all chats above.
Prioritize announcements, decisions, and concrete recommendations. Do not
repeat every per-chat summary — surface only the cross-cutting, highest-
value items.

Respond in Russian only.

## Output format (strict)

The output is rendered in Telegram with a Markdown-to-HTML converter that
recognises **only** these two markers:

- `**bold text**` — used for emphasised key terms,
- `[link text](https://...)` — used for clickable links.

Produce the daily digest in **exactly** this layout:

```
🔸 **Заголовок главного итога**: Краткое описание с **ключевыми терминами** и [ссылками](https://example.com), если уместно.

🔸 **Следующий итог**: ...
```

Rules — these are strict, the converter is intentionally limited so it can
catch prompt drift:

- Produce between 3 and 5 takeaways, each on its own block.
- Each takeaway MUST start with the orange diamond emoji `🔸` (U+1F538)
  followed by a single space, then a bold short headline, then `: `
  (colon + space), then the body on the same line.
- Takeaways MUST be separated by exactly one blank line.
- Inline within a body: use `**bold**` for emphasised terms and
  `[text](url)` for links.
- DO NOT use any of: `#`/`##`/`###` Markdown headers, `---` horizontal
  rules, bullet lists with `-`/`*`/`•`, numbered lists, single-asterisk
  `*italic*`, backtick code spans, raw HTML tags such as `<b>` or `<a>`.
- DO NOT prepend or append any explanatory prose, code fences, or
  meta-commentary outside the format above.
- Respond in Russian only.
