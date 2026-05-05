# Log

Append-only record of all wiki activity. Never edit past entries.

---

## [2026-05-04] ingest | ClassApp Notifier — debugging and final fixes

- Discovered GraphQL endpoint is `web.classapp.com.br/graphql` (single endpoint, not URL-keyword filtered)
- Correct JSON path: `data.node.messages.nodes[]` with fields `summary`, `entity.fullname`, `sentAt`
- Apollo Client caching prevents detail payload capture via network — switched to clicking message rows
- Body extraction via `document.body.innerText` slicing: last subject occurrence → first "Responder" line
- `#MessageReplies` content excluded by stopping at any line that appears in that element
- Images: CDN (403 on page.request) and Telegram URL (400) both failed; fixed by intercepting browser's own response bytes (`classapp-live-media` URL filter)
- Two-step login fixed: email → "Continuar" → password
- Updated wiki pages: Scraper, Notifier, NetworkInterception, overview

## [2026-05-04] ingest | ClassApp Notifier — initial implementation

- Built `app/` with scraper, notifier, state, and main entry point
- Playwright + network interception approach chosen over DOM scraping
- Telegram Bot API via requests (no extra library)
- Commands: `setup`, `get-chat-id`, `test-telegram`, `run`, `watch`
- Created wiki pages: Scraper, Notifier, MessageState, NetworkInterception, overview

## [2026-05-04] init | Wiki initialized

- Created wiki structure: `CLAUDE.md`, `index.md`, `log.md`, `overview.md`
- Created directories: `components/`, `concepts/`, `sources/`, `raw/`
- Domain: technical knowledge base for the ClassApp project
- Starting fresh — no sources ingested yet
