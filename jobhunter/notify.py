from __future__ import annotations

import logging
import os
from typing import Protocol

import requests

log = logging.getLogger(__name__)

TELEGRAM_API = "https://api.telegram.org/bot{token}/sendMessage"


class Notifier(Protocol):
    def send(self, message: str) -> None:
        """Deliver a short text update."""


class ConsoleNotifier:
    def send(self, message: str) -> None:
        print(message)


class TelegramNotifier:
    def __init__(self, token: str, chat_id: str) -> None:
        self.token = token
        self.chat_id = chat_id

    def send(self, message: str) -> None:
        url = TELEGRAM_API.format(token=self.token)
        response = requests.post(
            url,
            json={"chat_id": self.chat_id, "text": message, "disable_web_page_preview": True},
            timeout=20,
        )
        response.raise_for_status()


def get_notifier() -> Notifier:
    """Telegram when both env vars exist; otherwise print to the console."""

    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    chat_id = os.environ.get("TELEGRAM_CHAT_ID")
    if token and chat_id:
        return TelegramNotifier(token, chat_id)
    log.info("Telegram env vars not set; notifying on stdout")
    return ConsoleNotifier()


def format_digest(rows: list[dict[str, object]], heading: str = "Job hunt digest") -> str:
    if not rows:
        return f"{heading}: no matches"
    lines = [heading, ""]
    for row in rows:
        score = row.get("score", "?")
        title = row.get("title", "")
        company = row.get("company", "")
        url = row.get("url", "")
        lines.append(f"[{score}] {title} @ {company}")
        if url:
            lines.append(str(url))
        lines.append("")
    return "\n".join(lines).strip()
