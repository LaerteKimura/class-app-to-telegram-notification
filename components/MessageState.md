---
type: component
tags: [state, deduplication]
created: 2026-05-04
updated: 2026-05-04
---

# MessageState

`app/state.py` — Tracks which message IDs have already been sent to Telegram.

## Responsibilities

- Load seen IDs from `state.json` on startup.
- Expose `is_seen(id)` and `mark_seen(id)`.
- Persist back to disk after each check cycle.
- Cap the seen set at 2000 entries (oldest dropped) to prevent unbounded growth.

## Deduplication Logic

All new messages (not in state) are marked seen after each check cycle, regardless of whether they matched the keyword filter. This ensures a message that was filtered out once isn't re-evaluated on the next run, which would cause it to always appear "new."

If you want to re-deliver a message (e.g. after changing filters), delete `state.json` and run again.

## Related

- [[Scraper]]
- [[Notifier]]
