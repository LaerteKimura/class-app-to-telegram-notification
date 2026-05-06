import json
import logging
import os
from collections import defaultdict
from pathlib import Path

from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeout

logger = logging.getLogger(__name__)

_DATA_DIR = Path(os.environ.get("CLASSAPP_DATA", Path(__file__).parent))
SESSION_FILE = _DATA_DIR / "session.json"
NETWORK_LOG_FILE = _DATA_DIR / "network_log.json"

GRAPHQL_HOST = "web.classapp.com.br/graphql"


class ClassAppScraper:
    def __init__(self, config: dict):
        cfg = config["classapp"]
        self._login_url = cfg["login_url"]
        self._email = cfg["email"]
        self._password = cfg["password"]
        # Support both old format (single messages_url) and new format (children list)
        if "children" in cfg:
            self._children = cfg["children"]
        else:
            self._children = [{"name": "", "messages_url": cfg["messages_url"]}]

    @property
    def _first_url(self) -> str:
        return self._children[0]["messages_url"]

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

            page.goto(self._first_url)

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

            page.goto(self._first_url)

            input("\nClick a message to open it, then press Enter...")

            detail_log = Path(__file__).parent / "detail_log.json"
            detail_log.write_text(
                json.dumps(captured, indent=2, ensure_ascii=False),
                encoding="utf-8",
            )
            logger.info(f"Detail log saved → {detail_log} ({len(captured)} responses)")

            context.storage_state(path=str(SESSION_FILE))
            browser.close()

    def get_all_messages(self, headless: bool = True) -> list[dict]:
        """Return messages for all children in a single browser session.

        Messages that appear for more than one child are deduplicated and sent
        without a child label. Messages specific to one child are labelled.
        """
        per_child: list[tuple[str, str, list[dict]]] = []  # (name, url, messages)

        with sync_playwright() as p:
            browser = p.chromium.launch(headless=headless)
            context = self._load_context(browser)
            page = context.new_page()

            for child in self._children:
                child_name = child.get("name", "")
                messages_url = child["messages_url"]
                intercepted: list[dict] = []

                handler = lambda r, buf=intercepted: self._try_capture_messages(r, buf)
                page.on("response", handler)

                try:
                    page.goto(messages_url, timeout=30_000)

                    if self._needs_login(page):
                        self._login(page)
                        page.goto(messages_url, timeout=30_000)

                    page.wait_for_load_state("networkidle", timeout=20_000)
                    page.wait_for_timeout(2_000)

                except PlaywrightTimeout:
                    page.screenshot(path="debug_screenshot.png")
                    logger.warning(f"[{child_name}] Page load timed out.")
                except Exception:
                    page.screenshot(path="debug_screenshot.png")
                    raise
                finally:
                    page.remove_listener("response", handler)

                seen: set[str] = set()
                unique: list[dict] = []
                for m in intercepted:
                    if m["id"] not in seen:
                        seen.add(m["id"])
                        unique.append(m)

                per_child.append((child_name, messages_url, unique))
                logger.info(f"[{child_name or 'child'}] Captured {len(unique)} unique messages.")

            context.storage_state(path=str(SESSION_FILE))
            browser.close()

        # Deduplicate only by exact message ID.
        # Messages with different IDs are always sent separately, each with their
        # child label. Only if the exact same ID appears for multiple children is
        # the message sent once without a label.
        id_to_children: dict[str, set[str]] = defaultdict(set)
        id_to_msg: dict[str, dict] = {}
        id_order: list[str] = []

        for child_name, messages_url, messages in per_child:
            for m in messages:
                msg_id = m["id"]
                if msg_id not in id_to_msg:
                    id_to_msg[msg_id] = m
                    id_order.append(msg_id)
                    m["_list_url"] = messages_url
                id_to_children[msg_id].add(child_name)

        result: list[dict] = []
        for msg_id in id_order:
            msg = id_to_msg[msg_id]
            children = id_to_children[msg_id]
            msg["child"] = next(iter(children)) if len(children) == 1 else ""
            result.append(msg)

        return result

    def enrich_with_bodies(self, messages: list[dict]) -> None:
        """Click each message to capture body and images. Groups by child to avoid
        unnecessary page navigation."""
        if not messages:
            return

        groups: dict[str, list[dict]] = defaultdict(list)
        for m in messages:
            groups[m.get("_list_url", self._first_url)].append(m)

        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            context = self._load_context(browser)
            page = context.new_page()

            try:
                for list_url, group in groups.items():
                    page.goto(list_url, timeout=30_000)
                    if self._needs_login(page):
                        self._login(page)
                        page.goto(list_url, timeout=30_000)
                    page.wait_for_load_state("networkidle", timeout=20_000)
                    page.wait_for_timeout(2_000)

                    for msg in group:
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
            for selector in [
                f'[data-id="{target_id}"]',
                f'[data-message-id="{target_id}"]',
            ]:
                el = page.query_selector(selector)
                if el:
                    el.click()
                    clicked = True
                    break

            if not clicked and subject:
                try:
                    page.locator(f'text="{subject}"').first.click(timeout=5_000)
                    clicked = True
                except Exception:
                    pass

            if not clicked:
                logger.debug(f"Could not find message {target_id} in DOM")
                return

            page.wait_for_timeout(3_000)

            screenshot = Path(__file__).parent / "debug_detail.png"
            if not screenshot.exists():
                page.screenshot(path=str(screenshot))
                logger.info(f"Screenshot saved → {screenshot}")

            msg["body"]   = self._extract_from_dom(page, subject)
            msg["images"] = list(captured_images)

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

                let subjectIdx = -1;
                for (let i = lines.length - 1; i >= 0; i--) {
                    if (lines[i] === subjectTrim) { subjectIdx = i; break; }
                }
                if (subjectIdx < 0) return '';

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

        node = inner.get("node") or {}
        node_entity_id = str(node.get("id", ""))
        nodes = node.get("messages", {}).get("nodes", [])

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
