# Summary task

You are summarizing one topic-chat from a private Telegram group for a
single operator who wants a digest of the last working period.

**Chat name**: {{chat_name}}

## Messages

Each line below is one message in chronological order and has the form:

```
[<ISO-8601 timestamp>] <Sender>: <text>
```

When a message is a reply to another message from the same window, the line
has the form:

```
[<ISO-8601 timestamp>] <Sender> [reply to: <parent_id>]: <text>
```

A message line whose text body is empty represents a media attachment or a
service/system message (for example a photo, voice note, or status update
with no textual caption). You must acknowledge such activity in the summary
instead of silently ignoring it — mention that media or service activity
happened, ideally with the sender and timestamp, so the operator is not
surprised by the gap in the textual record.

{{messages}}

## Your task

Write a concise summary **in Russian** of what happened in this chat during
the window. Highlight:

- key announcements,
- concrete tool or product recommendations,
- technical solutions or fixes that were shared,
- notable discussions or open questions.

Keep the tone operational and factual. Do not invent details that are not
in the transcript. Respond in Russian only.

## Output format (strict)

The output is rendered in Telegram with a Markdown-to-HTML converter that
recognises **only** these two markers:

- `**bold text**` — used for the title and for emphasised key terms,
- `[link text](https://...)` — used for clickable links.

Produce the summary in **exactly** this layout:

```
**Сводка чата "{{chat_name}}" за DD.MM.YYYY**

🔸 **Название темы**: Краткое описание с **ключевыми терминами** и [ссылками](https://example.com), если уместно.

🔸 **Следующая тема**: ...
```

Rules — these are strict, the converter is intentionally limited so it can
catch prompt drift:

- The very first line MUST be the bold title in the form
  `**Сводка чата "{{chat_name}}" за DD.MM.YYYY**`. Use today's date in
  Russian `DD.MM.YYYY` form (zero-padded), based on the latest message
  timestamp in the transcript.
- Each topic MUST start with the orange diamond emoji `🔸` (U+1F538) followed
  by a single space, then the bold topic name, then `: ` (colon + space),
  then the topic body on the same line.
- Topics MUST be separated by exactly one blank line.
- Inline within a topic body: use `**bold**` for emphasised terms and
  `[text](url)` for links. Plain-text URLs without `[…](…)` are allowed but
  will not be clickable.
- DO NOT use any of: `#`/`##`/`###` Markdown headers, `---` horizontal
  rules, bullet lists with `-`/`*`/`•`, numbered lists, single-asterisk
  `*italic*`, backtick code spans, raw HTML tags such as `<b>` or `<a>`.
- DO NOT prepend or append any explanatory prose, code fences, or
  meta-commentary outside the format above.
- Respond in Russian only.
