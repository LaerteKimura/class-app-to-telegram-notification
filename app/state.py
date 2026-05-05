import json
import os
from pathlib import Path

_DATA_DIR = Path(os.environ.get("CLASSAPP_DATA", Path(__file__).parent))
STATE_FILE = _DATA_DIR / "state.json"
MAX_SEEN = 2000


class MessageState:
    def __init__(self):
        self._seen: set[str] = set()
        self._load()

    def _load(self):
        if STATE_FILE.exists():
            data = json.loads(STATE_FILE.read_text(encoding="utf-8"))
            self._seen = set(data.get("seen", []))

    def is_seen(self, message_id: str) -> bool:
        return message_id in self._seen

    def mark_seen(self, message_id: str):
        self._seen.add(message_id)

    def save(self):
        seen_list = list(self._seen)
        if len(seen_list) > MAX_SEEN:
            seen_list = seen_list[-MAX_SEEN:]
        STATE_FILE.write_text(
            json.dumps({"seen": seen_list}, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
