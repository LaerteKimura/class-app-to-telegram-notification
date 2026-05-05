---
type: component
tags: [telegram, notification]
created: 2026-05-04
updated: 2026-05-04
---

# Notifier

`app/notifier.py` — Sends formatted messages and images to Telegram via the Bot API.

## Responsibilities

- Format a message dict into a Telegram Markdown message with Brazilian date/time.
- Upload any attached images as separate `sendPhoto` calls (multipart bytes upload).
- Provide `test()` and `get_chat_id()` helpers for initial setup.

## Message Format

```
📚 *ClassApp - Nova Mensagem (DD/MM/YYYY HH:MM)*

*Assunto:* <subject>
*De:* <sender>

<full body text>

[Ver mensagem](<url>)
```

Fields are omitted if empty. Body is the full text captured from the modal — no truncation. Date is converted to BRT (UTC-3) and formatted as `DD/MM/YYYY HH:MM`.

## Image Delivery

Images are received as `list[bytes]` in `message["images"]`. Each is uploaded via `sendPhoto` with multipart form data:

```python
requests.post(
    url,
    data={"chat_id": self._chat_id},
    files={"photo": (f"image_{i}.jpg", img_bytes, "image/jpeg")},
)
```

Sending a CDN URL directly to Telegram fails (400 Bad Request — Telegram cannot fetch auth-gated CDN URLs). Sending bytes works.

## Brazilian Timezone

All dates from ClassApp are ISO 8601 UTC. `_format_date()` converts to BRT (UTC-3):

```python
BRT = timezone(timedelta(hours=-3))
dt.astimezone(BRT).strftime("%d/%m/%Y %H:%M")
```

## Markdown Escaping

`_escape()` backslash-escapes `_`, `*`, `[`, `]`, `` ` `` so Markdown formatting in the body text does not break Telegram's parser.

## Setup Flow

1. Create a bot via @BotFather on Telegram → get `bot_token`.
2. Set `bot_token` in `config.yaml`.
3. Send any message to the bot.
4. Run `python main.py get-chat-id` → prints your `chat_id`.
5. Set `chat_id` in `config.yaml`.
6. Run `python main.py test-telegram` to confirm.

## Related

- [[Scraper]]
- [[MessageState]]
- [[overview]]
