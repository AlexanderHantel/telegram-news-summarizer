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
