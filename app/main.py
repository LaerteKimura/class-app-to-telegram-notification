import argparse
import logging
import os
import sys
import time
from pathlib import Path

import schedule
import yaml

from notifier import TelegramNotifier
from scraper import ClassAppScraper
from state import MessageState

_DATA_DIR = Path(os.environ.get("CLASSAPP_DATA", Path(__file__).parent))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(_DATA_DIR / "notifier.log", encoding="utf-8"),
    ],
)
logger = logging.getLogger(__name__)


def load_config() -> dict:
    path = Path(__file__).parent / "config.yaml"
    if not path.exists():
        logger.error("config.yaml not found. See README for setup instructions.")
        sys.exit(1)
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f)


def matches_filters(message: dict, keywords: list[str]) -> bool:
    if not keywords:
        return True
    subject = message.get("subject", "").lower()
    return any(kw.lower() in subject for kw in keywords)


def check_once(config: dict, headless: bool = True):
    scraper = ClassAppScraper(config)
    notifier = TelegramNotifier(config)
    state = MessageState()
    keywords: list[str] = config.get("filters", {}).get("keywords", [])

    logger.info("Checking ClassApp for new messages…")
    try:
        messages = scraper.get_messages(headless=headless)
    except Exception as e:
        logger.error(f"Failed to fetch messages: {e}")
        return

    new = [m for m in messages if not state.is_seen(m["id"])]
    to_send = [m for m in new if matches_filters(m, keywords)]

    logger.info(f"{len(messages)} total | {len(new)} new | {len(to_send)} match filter")

    if to_send:
        scraper.enrich_with_bodies(to_send)

    for msg in to_send:
        try:
            notifier.send(msg)
            logger.info(f"Sent: {msg.get('subject', '(no subject)')}")
        except Exception as e:
            logger.error(f"Telegram error for message {msg.get('id')}: {e}")

    for msg in new:
        state.mark_seen(msg["id"])
    state.save()


def cmd_setup(config: dict):
    ClassAppScraper(config).setup_session()


def cmd_run(config: dict, visible: bool, debug: bool = False):
    if debug:
        logging.getLogger().setLevel(logging.DEBUG)
    check_once(config, headless=not visible)


def cmd_watch(config: dict):
    hours: float = config.get("schedule", {}).get("interval_hours", 12)
    logger.info(f"Watcher started — checking every {hours} hour(s). Press Ctrl+C to stop.")

    check_once(config)  # run immediately on start

    schedule.every(hours).hours.do(check_once, config=config)
    while True:
        schedule.run_pending()
        time.sleep(60)


def cmd_test_telegram(config: dict):
    TelegramNotifier(config).test()


def cmd_get_chat_id(config: dict):
    TelegramNotifier(config).get_chat_id()


def main():
    parser = argparse.ArgumentParser(
        description="ClassApp → Telegram notifier",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
commands:
  setup            Open browser to log in and save session (run this first)
  get-chat-id      Print your Telegram chat_id (after setting bot_token in config.yaml)
  test-telegram    Send a test message to Telegram
  run              Check once and send new messages
  watch            Run on schedule (interval_hours from config.yaml)
        """,
    )
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("setup", help="Open browser for first-time login")
    sub.add_parser("setup-detail", help="Capture the GraphQL response when clicking a message")
    sub.add_parser("get-chat-id", help="Print Telegram chat_id")
    sub.add_parser("test-telegram", help="Send a test Telegram message")

    run_p = sub.add_parser("run", help="Check once")
    run_p.add_argument("--visible", action="store_true", help="Show browser window")
    run_p.add_argument("--debug", action="store_true", help="Verbose logging")

    sub.add_parser("watch", help="Run on schedule")

    args = parser.parse_args()
    config = load_config()

    commands = {
        "setup": lambda: cmd_setup(config),
        "setup-detail": lambda: ClassAppScraper(config).setup_detail(),
        "get-chat-id": lambda: cmd_get_chat_id(config),
        "test-telegram": lambda: cmd_test_telegram(config),
        "run": lambda: cmd_run(config, getattr(args, "visible", False), getattr(args, "debug", False)),
        "watch": lambda: cmd_watch(config),
    }
    commands[args.command]()


if __name__ == "__main__":
    main()
