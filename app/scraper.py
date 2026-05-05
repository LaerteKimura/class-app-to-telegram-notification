import json
import logging
import os
from pathlib import Path

from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeout

logger = logging.getLogger(__name__)

_DATA_DIR = Path(os.environ.get("CLASSAPP_DATA", Path(__file__).parent))
SESSION_FILE = _DATA_DIR / "session.json"
NETWORK_LOG_FILE = _DATA_DIR / "network_log.json"

GRAPHQL_HOST = "web.classapp.com.br/graphql"


class ClassAppScraper:
    def __init__(self, config: dict):
        self._login_url = config["classapp"]["login_url"]
        self._messages_url = config["classapp"]["messages_url"]
        self._email = config["classapp"]["email"]
        self._password = config["classapp"]["password"]

    # ------------------------------------------------------------------
    # Public
    # ------------------------------------------------------------------

    def setup_session(self):
        """Open a visible browser for manual login. Saves session + network log."""
        logger.info("Opening browser. Log in to ClassApp and navigate to your messages page.")
        logger.info("When you can see the messages list, press Enter here to save the session.")

        with sync_playwright() as p:
            browser = p.chromium.launch(headless=False)
            context = browser.new_context()
            page = context.new_page()

            captured: list[dict] = []
            page.on("response", lambda r: self._capture_all_json(r, captured))

            page.goto(self._messages_url)

            input("\nPress Enter when the messages page is loaded and you can see the list...")

            context.storage_state(path=str(SESSION_FILE))
            logger.info(f"Session saved → {SESSION_FILE}")

            if captured:
                NETWORK_LOG_FILE.write_text(
                    json.dumps(captured[:30], indent=2, ensure_ascii=False),
                    encoding="utf-8",
                )
                logger.info(f"Network log saved → {NETWORK_LOG_FILE}")

            browser.close()

    def setup_detail(self):
        """Open browser on the messages page. Click ONE message to open its detail,
        then press Enter. Saves the captured GraphQL responses to detail_log.json."""
        logger.info("Opening browser on the messages page.")
        logger.info("Click on ONE message to open its detail view, then press Enter here.")

        with sync_playwright() as p:
            browser = p.chromium.launch(headless=False)
            context = self._load_context(browser)
            page = context.new_page()

            captured: list[dict] = []
            page.on("response", lambda r: self._capture_all_json(r, captured))

            page.goto(self._messages_url)

            input("\nClick a message to open it, then press Enter...")

            detail_log = Path(__file__).parent / "detail_log.json"
            detail_log.write_text(
                json.dumps(captured, indent=2, ensure_ascii=False),
                encoding="utf-8",
            )
            logger.info(f"Detail log saved → {detail_log} ({len(captured)} responses)")

            context.storage_state(path=str(SESSION_FILE))
            browser.close()

    def get_messages(self, headless: bool = True) -> list[dict]:
        """Return the list of messages from the messages page (without bodies)."""
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=headless)
            context = self._load_context(browser)
            page = context.new_page()

            intercepted: list[dict] = []
            page.on("response", lambda r: self._try_capture_messages(r, intercepted))

            try:
                page.goto(self._messages_url, timeout=30_000)

                if self._needs_login(page):
                    self._login(page)
                    page.goto(self._messages_url, timeout=30_000)

                page.wait_for_load_state("networkidle", timeout=20_000)
                page.wait_for_timeout(2_000)

            except PlaywrightTimeout:
                page.screenshot(path="debug_screenshot.png")
                logger.warning("Page load timed out. Screenshot saved to debug_screenshot.png.")
            except Exception:
                page.screenshot(path="debug_screenshot.png")
                raise
            finally:
                context.storage_state(path=str(SESSION_FILE))
                browser.close()

        # Deduplicate — same message can appear for multiple children
        seen_ids: set[str] = set()
        unique: list[dict] = []
        for m in intercepted:
            if m["id"] not in seen_ids:
                seen_ids.add(m["id"])
                unique.append(m)

        if not unique:
            logger.warning("No messages captured. Run 'python main.py setup' if this is the first run.")
        else:
            logger.info(f"Captured {len(unique)} unique messages.")

        return unique

    def enrich_with_bodies(self, messages: list[dict]) -> None:
        """Click each message in the list to trigger the detail load, capture the body.

        Only called for new messages we intend to send, so typically 0–5 clicks.
        """
        if not messages:
            return

        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            context = self._load_context(browser)
            page = context.new_page()

            try:
                # Load the messages list first
                page.goto(self._messages_url, timeout=30_000)
                if self._needs_login(page):
                    self._login(page)
                    page.goto(self._messages_url, timeout=30_000)
                page.wait_for_load_state("networkidle", timeout=20_000)
                page.wait_for_timeout(2_000)

                list_url = page.url

                for msg in messages:
                    self._click_and_capture_body(page, msg, list_url)
            finally:
                context.storage_state(path=str(SESSION_FILE))
                browser.close()

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _click_and_capture_body(self, page, msg: dict, list_url: str) -> None:
        """Click a message row, extract body text and images, store in msg in-place."""
        target_id = msg["id"]
        subject = msg.get("subject", "")
        msg["body"] = ""
        msg["images"] = []

        # Capture image bytes from responses as the browser loads them naturally
        captured_images: list[bytes] = []

        def on_response(response):
            if response.status == 200 and "classapp-live-media" in response.url:
                try:
                    captured_images.append(response.body())
                except Exception:
                    pass

        page.on("response", on_response)
        clicked = False

        try:
            # Try data-id attributes first
            for selector in [
                f'[data-id="{target_id}"]',
                f'[data-message-id="{target_id}"]',
            ]:
                el = page.query_selector(selector)
                if el:
                    el.click()
                    clicked = True
                    break

            # Fall back: click by subject text
            if not clicked and subject:
                try:
                    page.locator(f'text="{subject}"').first.click(timeout=5_000)
                    clicked = True
                except Exception:
                    pass

            if not clicked:
                logger.debug(f"Could not find message {target_id} in DOM")
                return

            # Wait for panel/modal and images to fully load
            page.wait_for_timeout(3_000)

            # Save a screenshot for the first message to verify what opened
            screenshot = Path(__file__).parent / "debug_detail.png"
            if not screenshot.exists():
                page.screenshot(path=str(screenshot))
                logger.info(f"Screenshot saved → {screenshot}")

            msg["body"]   = self._extract_from_dom(page, subject)
            msg["images"] = list(captured_images)

            # Close the panel
            page.keyboard.press("Escape")
            page.wait_for_timeout(500)
            if page.url != list_url:
                page.go_back(timeout=10_000)
                page.wait_for_load_state("networkidle", timeout=10_000)
                page.wait_for_timeout(1_000)

        except Exception as e:
            logger.debug(f"Error processing message {target_id}: {e}")
            try:
                page.goto(list_url, timeout=15_000)
                page.wait_for_load_state("networkidle", timeout=10_000)
            except Exception:
                pass
        finally:
            page.remove_listener("response", on_response)

        logger.debug(
            f"Message {target_id}: body={len(msg['body'])} chars, "
            f"images={len(msg['images'])}"
        )

    def _extract_from_dom(self, page, subject: str) -> str:
        """Extract message body from the open modal using full-page text slicing.

        React portals render the modal at the end of <body>, so the modal's
        subject heading is the LAST occurrence of that text in the page.
        We slice from there, stopping at either #MessageReplies or the reply box.
        """
        return page.evaluate(
            """([subject]) => {
                const subjectTrim = subject.trim();

                // Collect lines from #MessageReplies so we know where to stop
                const repliesEl = document.getElementById('MessageReplies');
                const repliesLines = new Set(
                    repliesEl
                        ? repliesEl.innerText.split('\\n').map(l => l.trim()).filter(Boolean)
                        : []
                );

                const lines = document.body.innerText
                    .split('\\n')
                    .map(l => l.trim())
                    .filter(Boolean);

                // Last occurrence of the subject = the modal heading
                let subjectIdx = -1;
                for (let i = lines.length - 1; i >= 0; i--) {
                    if (lines[i] === subjectTrim) { subjectIdx = i; break; }
                }
                if (subjectIdx < 0) return '';

                // Stop at the first line that belongs to MessageReplies OR the reply box
                let endIdx = lines.length;
                for (let i = subjectIdx + 1; i < lines.length; i++) {
                    const l = lines[i];
                    if (l.toLowerCase().startsWith('responder') ||
                        l.toLowerCase().startsWith('reply')) {
                        endIdx = i; break;
                    }
                    if (repliesLines.size > 0 && repliesLines.has(l)) {
                        endIdx = i; break;
                    }
                }

                return lines.slice(subjectIdx + 1, endIdx).join('\\n').trim();
            }""",
            [subject],
        )

    def _load_context(self, browser):
        if SESSION_FILE.exists():
            logger.info("Resuming saved session.")
            return browser.new_context(storage_state=str(SESSION_FILE))
        logger.info("No saved session — will log in.")
        return browser.new_context()

    def _needs_login(self, page) -> bool:
        url = page.url.lower()
        return any(k in url for k in ["login", "signin", "auth", "entrar"])

    def _login(self, page):
        logger.info("Logging in to ClassApp...")
        page.goto(self._login_url)
        page.wait_for_load_state("networkidle")

        # Step 1: email → Continue
        email_selector = 'input[type="email"], input[name="email"], input[name="username"]'
        page.wait_for_selector(email_selector, timeout=10_000)
        page.fill(email_selector, self._email)
        page.click(
            'button:has-text("Continuar"), '
            'button:has-text("Continue"), '
            'button:has-text("Próximo"), '
            'button:has-text("Next"), '
            'button[type="submit"]'
        )

        # Step 2: password → submit
        password_selector = 'input[type="password"], input[name="password"]'
        page.wait_for_selector(password_selector, timeout=10_000)
        page.fill(password_selector, self._password)
        page.click(
            'button[type="submit"], '
            'button:has-text("Entrar"), '
            'button:has-text("Login"), '
            'button:has-text("Acessar")'
        )
        page.wait_for_load_state("networkidle", timeout=20_000)

        if self._needs_login(page):
            raise RuntimeError("Login failed. Check your email and password in config.yaml.")
        logger.info("Login successful.")

    def _download_images(self, page, subject: str) -> list[bytes]:
        """Extract content image URLs then download them via the authenticated session."""
        urls = self._extract_images_from_dom(page, subject)
        downloaded = []
        for url in urls:
            try:
                resp = page.request.get(url, timeout=15_000)
                if resp.ok:
                    downloaded.append(resp.body())
                    logger.debug(f"Downloaded image {len(downloaded)}: {len(resp.body())} bytes")
                else:
                    logger.debug(f"Image fetch failed ({resp.status}): {url}")
            except Exception as e:
                logger.debug(f"Image download error: {e}")
        return downloaded

    def _extract_images_from_dom(self, page, subject: str) -> list[str]:
        """Return content image URLs — identified by data-action='open-media-item'."""
        return page.evaluate(
            """() => {
                return Array.from(
                    document.querySelectorAll('img[data-action="open-media-item"]')
                )
                .map(img => img.src)
                .filter((src, idx, arr) => src && arr.indexOf(src) === idx);
            }"""
        )

    def _try_capture_messages(self, response, out: list):
        """Intercept ClassApp GraphQL responses and extract message list nodes."""
        if response.status != 200:
            return
        if GRAPHQL_HOST not in response.url:
            return

        try:
            data = response.json()
        except Exception:
            return

        found = self._normalize_graphql(data)
        if found:
            logger.debug(f"graphql response → {len(found)} messages extracted")
        out.extend(found)

    def _normalize_graphql(self, data: dict) -> list[dict]:
        """
        ClassApp GraphQL response shape (messages page):
          data.node.messages.nodes[]
        Each node: { id, summary, entity{fullname}, sentAt, ... }
        """
        inner = data.get("data", {})

        # Primary: data.node.messages.nodes
        node = inner.get("node", {})
        node_entity_id = str(node.get("id", ""))
        nodes = node.get("messages", {}).get("nodes", [])

        # Fallback: scan data.viewer.*.nodes for anything with "summary"
        if not nodes:
            for value in inner.get("viewer", {}).values():
                if isinstance(value, dict):
                    candidates = value.get("nodes", [])
                    if candidates and isinstance(candidates[0], dict) and "summary" in candidates[0]:
                        nodes = candidates
                        break

        out = []
        for item in nodes:
            msg_id = str(item.get("id", ""))
            if not msg_id:
                continue
            entity = item.get("entity") or {}
            out.append({
                "id": msg_id,
                "subject": item.get("summary", ""),
                "sender": entity.get("fullname", ""),
                "date": item.get("sentAt") or item.get("created") or "",
                "body": "",
                "url": (
                    f"https://classapp.com.br/entities/{node_entity_id}/messages/{msg_id}"
                    if node_entity_id else ""
                ),
            })
        return out

    def _capture_all_json(self, response, out: list):
        """Capture every JSON response (setup/debug mode)."""
        if response.status != 200:
            return
        if "text/html" in response.headers.get("content-type", ""):
            return
        try:
            out.append({"url": response.url, "data": response.json()})
        except Exception:
            pass
