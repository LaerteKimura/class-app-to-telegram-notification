---
type: concept
tags: [playwright, spa, graphql, apollo, scraping-strategy]
created: 2026-05-04
updated: 2026-05-04
---

# Network Interception

Why and how the scraper captures API/image responses instead of parsing the DOM, and where DOM scraping is still used.

## The Problem with DOM Scraping SPAs

ClassApp is a React SPA. CSS class names and DOM hierarchy can change with any frontend deploy. Hardcoded selectors break silently — the scraper runs, finds nothing, and reports zero messages with no error.

## GraphQL Interception (Message List)

ClassApp uses a single Apollo GraphQL endpoint: `web.classapp.com.br/graphql`. Playwright's `page.on("response", handler)` fires for every HTTP response. Filtering to that host and parsing the JSON is stable — API contracts change far less than UI markup.

Response path for the message list:

```
data.node.messages.nodes[]  →  id, summary, entity.fullname, sentAt
```

## Apollo Client Caching (Why We Click)

Apollo Client caches GraphQL responses in memory. If a message's detail was already fetched in the current SPA session, navigating to its URL or calling the query again serves the cached result — no new network request fires. `page.on("response", ...)` never sees the detail payload.

**Consequence**: body text cannot be captured via GraphQL interception for detail views. The scraper instead clicks each message row to open the panel and reads the body from the DOM.

## DOM Text Slicing (Body)

React renders the message modal via a portal at the end of `<body>`. The body is extracted by:

1. Splitting `document.body.innerText` into lines.
2. Finding the **last** occurrence of the subject text (the modal heading is always the last because portals render at the end of the DOM).
3. Slicing forward until "Responder"/"Reply" or a line from `#MessageReplies`.

This is a hybrid: the list uses network interception; the body uses DOM text slicing.

## Image Response Interception

Content images live at `images.classapp.com.br/…/classapp-live-media-1/…`. Two approaches failed:

| Approach | Failure |
|---|---|
| Send CDN URL to Telegram | 400 — Telegram cannot fetch auth-gated CDN |
| `page.request.get(url)` | 403 — `page.request` does not carry the browser's auth cookies |

**Working approach**: intercept the browser's own authenticated requests. The browser loads images naturally with its session cookies. The `on_response` listener captures the bytes:

```python
def on_response(response):
    if response.status == 200 and "classapp-live-media" in response.url:
        captured_images.append(response.body())
page.on("response", on_response)
# ... click message row ...
page.remove_listener("response", on_response)
```

The listener is scoped per-message to avoid cross-contamination.

## Tradeoffs

| | Network Interception | DOM Scraping |
|---|---|---|
| Stability | High (API contracts are stable) | Medium (innerText structure is stable even if CSS changes) |
| Fragility vector | API endpoint URL or schema | Page text layout changes |
| Used for | Message list (GraphQL), images | Message body |

## Related

- [[Scraper]]
