import logging
from datetime import datetime, timezone, timedelta

import requests

logger = logging.getLogger(__name__)

TELEGRAM_API = "https://api.telegram.org/bot{token}/{method}"
BRT = timezone(timedelta(hours=-3))


class TelegramNotifier:
    def __init__(self, config: dict):
        self._token = config["telegram"]["bot_token"]
        self._chat_id = config["telegram"]["chat_id"]

    def send(self, message: dict):
        subject = message.get("subject") or "(sem assunto)"
        sender  = message.get("sender", "")
        date    = self._format_date(message.get("date", ""))
        body    = message.get("body", "")
        url     = message.get("url", "")
        images  = message.get("images", [])

        lines = [f"📚 *ClassApp - Nova Mensagem ({self._escape(date)})*", ""]
        lines.append(f"*Assunto:* {self._escape(subject)}")
        if sender:
            lines.append(f"*De:* {self._escape(sender)}")
        if body:
            lines += ["", self._escape(body)]
        if url:
            lines += ["", f"[Ver mensagem]({url})"]

        self._post("sendMessage", {
            "chat_id": self._chat_id,
            "text": "\n".join(lines),
            "parse_mode": "Markdown",
            "disable_web_page_preview": True,
        })

        for i, img_bytes in enumerate(images):
            try:
                url = TELEGRAM_API.format(token=self._token, method="sendPhoto")
                resp = requests.post(
                    url,
                    data={"chat_id": self._chat_id},
                    files={"photo": (f"image_{i}.jpg", img_bytes, "image/jpeg")},
                    timeout=30,
                )
                resp.raise_for_status()
                logger.debug(f"Sent image {i + 1}/{len(images)}")
            except Exception as e:
                logger.warning(f"Could not send image {i + 1}: {e}")

    def test(self):
        self._post("sendMessage", {
            "chat_id": self._chat_id,
            "text": "✅ ClassApp Notifier está funcionando!",
        })
        logger.info("Test message sent to Telegram.")

    def get_chat_id(self):
        resp = requests.get(
            TELEGRAM_API.format(token=self._token, method="getUpdates"),
            timeout=10,
        )
        resp.raise_for_status()
        updates = resp.json().get("result", [])
        if not updates:
            print("No updates found. Send a message to your bot first, then run this again.")
            return
        for u in updates:
            chat = u.get("message", {}).get("chat", {})
            print(f"chat_id: {chat.get('id')}  type: {chat.get('type')}  name: {chat.get('first_name') or chat.get('title')}")

    def _post(self, method: str, payload: dict):
        url = TELEGRAM_API.format(token=self._token, method=method)
        resp = requests.post(url, json=payload, timeout=10)
        resp.raise_for_status()

    @staticmethod
    def _format_date(iso_str: str) -> str:
        if not iso_str:
            return ""
        try:
            dt = datetime.fromisoformat(iso_str.replace("Z", "+00:00"))
            return dt.astimezone(BRT).strftime("%d/%m/%Y %H:%M")
        except Exception:
            return iso_str

    @staticmethod
    def _escape(text: str) -> str:
        for ch in ["_", "*", "[", "]", "`"]:
            text = text.replace(ch, f"\\{ch}")
        return text
