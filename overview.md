---
type: overview
created: 2026-05-04
updated: 2026-05-04
---

# ClassApp — Project Overview

_Evolving synthesis of the ClassApp notifier project._

---

## What is ClassApp?

A Python automation tool that monitors the ClassApp school communication platform (classapp.com.br) and forwards new messages to Telegram. Parents get school notifications directly in Telegram without checking the web portal.

---

## Architecture

Three-layer pipeline:

1. **Scraper** (`scraper.py`) — Playwright opens ClassApp, intercepts the GraphQL API to get the message list, then clicks each new message to extract its body (DOM slicing) and images (response byte interception).
2. **Filter** (`main.py`) — Applies keyword rules on message subjects; marks all new IDs as seen regardless.
3. **Notifier** (`notifier.py`) — Formats a Markdown message and posts to Telegram via Bot API; images sent as multipart bytes uploads.

Session cookies are persisted in `session.json` — login only happens when the session expires. Seen message IDs are tracked in `state.json` (capped at 2000) to prevent duplicate sends.

---

## Data Flow

```
ClassApp web → [GraphQL /graphql] → message list (id, subject, sender, date, url)
                                       ↓
                              filter: new + keyword match
                                       ↓
                      [browser click each message]
                        ↓                    ↓
              DOM innerText slicing    response interception
                  (body text)           (image bytes)
                                       ↓
                            Telegram Bot API
                      sendMessage (Markdown) + sendPhoto (bytes)
```

---

## Key Components

- [[Scraper]] — Playwright scraper: GraphQL interception, DOM slicing, image byte interception
- [[Notifier]] — Telegram Bot API client: Markdown formatting, BRT timezone, multipart image upload
- [[MessageState]] — Seen-message deduplication via JSON state file

---

## Key Concepts & Decisions

- [[NetworkInterception]] — Hybrid strategy: GraphQL for list, DOM for body, response bytes for images

---

## Configuration (`config.yaml`)

```yaml
classapp:
  login_url:    https://classapp.com.br/login
  messages_url: https://classapp.com.br/entities/<entity_id>/messages
  email:        <email>
  password:     <password>
telegram:
  bot_token: <token>
  chat_id:   <chat_id>
schedule:
  interval_hours: 12
filters:
  keywords: []   # empty = all messages
```

## CLI Commands

| Command | Purpose |
|---|---|
| `setup` | First-time: open visible browser, log in manually, save session |
| `setup-detail` | Debug: click one message, save all GraphQL responses to `detail_log.json` |
| `get-chat-id` | Print your Telegram chat_id |
| `test-telegram` | Send a test message to confirm bot works |
| `run [--visible] [--debug]` | Check once and send new messages |
| `watch` | Run on schedule (interval_hours); blocks until Ctrl+C |

---

## Related

- [[index]]
