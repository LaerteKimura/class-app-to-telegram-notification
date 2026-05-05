---
type: component
tags: [playwright, scraping, classapp, graphql]
created: 2026-05-04
updated: 2026-05-04
---

# Scraper

`app/scraper.py` — Fetches messages from ClassApp using Playwright. Uses a hybrid strategy: GraphQL interception for the message list, DOM text slicing for the body, and response interception for images.

## Responsibilities

- Maintain a persistent browser session (`session.json`) to avoid re-login on every check.
- Intercept the GraphQL API to get the message list (subject, sender, date, URL).
- Click each new message in the browser to trigger body + image loading, then extract via DOM.
- Normalize all data to a standard schema: `{id, subject, sender, date, body, url, images}`.

## Key Methods

| Method | Purpose |
|---|---|
| `setup_session()` | Visible browser for first-time login; saves session + network log. |
| `setup_detail()` | Visible browser; user clicks one message; saves all GraphQL responses to `detail_log.json`. |
| `get_messages(headless)` | Returns normalized message list by intercepting the GraphQL API. |
| `enrich_with_bodies(messages)` | Clicks each message in the browser; fills `body` and `images` in-place. |
| `_click_and_capture_body(page, msg, list_url)` | Clicks one message row, waits, extracts body and images, closes panel. |
| `_extract_from_dom(page, subject)` | Slices `document.body.innerText` to get modal body text. |
| `_login(page)` | Two-step login: email → "Continuar" button → password → submit. |
| `_try_capture_messages(response, out)` | Filters to GraphQL host; delegates to `_normalize_graphql`. |
| `_normalize_graphql(data)` | Maps `data.node.messages.nodes[]` fields to standard schema. |

## GraphQL Interception

ClassApp uses a single Apollo GraphQL endpoint: `web.classapp.com.br/graphql`. The message list is in:

```
data.node.messages.nodes[]
  id        → message id
  summary   → subject
  entity.fullname → sender
  sentAt    → date (ISO 8601 UTC)
```

The `node.id` at the root level is the entity/child ID — used to build the `url` field:
`https://classapp.com.br/entities/{entity_id}/messages/{msg_id}`

## Apollo Client Caching Problem

ClassApp uses Apollo Client, which caches GraphQL responses. Navigating directly to a message URL does not trigger a new network request — the detail data is served from the in-memory cache. This means `page.on("response", ...)` never fires for the body content.

**Solution**: open the messages list page, then click each message row in the DOM to trigger the panel/modal. The modal loads body and images as the browser makes authenticated requests naturally.

## Body Extraction — DOM Text Slicing

React renders the message modal via a portal at the end of `<body>`. `_extract_from_dom()` works by:

1. Splitting `document.body.innerText` into trimmed, non-empty lines.
2. Finding the **last** occurrence of the subject text (= the modal heading, not the list row).
3. Slicing from there until the first line that starts with "Responder"/"Reply" **or** until a line that belongs to `#MessageReplies`.

This excludes the reply thread appended below the original message.

## Image Interception

Images inside a message body are served from `images.classapp.com.br/…/classapp-live-media-1/…`. The CDN requires auth cookies that are not available to `page.request.get()` (gets 403). Instead, the scraper intercepts the browser's own authenticated requests:

```python
def on_response(response):
    if response.status == 200 and "classapp-live-media" in response.url:
        captured_images.append(response.body())
page.on("response", on_response)
# ... click the message row ...
msg["images"] = list(captured_images)
page.remove_listener("response", on_response)
```

The listener is registered before the click and removed after extraction to avoid leaking across messages.

## Session Persistence

After every browser session the context (cookies, localStorage, sessionStorage) is saved to `session.json` via `context.storage_state()`. On the next run it is restored. If ClassApp redirects to a login URL, `_needs_login()` detects it and re-authenticates automatically.

## Two-Step Login

ClassApp's login is a two-step form: first ask for email and show "Continuar", then ask for password. `_login()` handles both steps with `wait_for_selector` between them to wait for each form to render.

## Related

- [[Notifier]]
- [[MessageState]]
- [[NetworkInterception]]
- [[overview]]
