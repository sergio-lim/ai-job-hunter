from __future__ import annotations

from jobhunter.notify import ConsoleNotifier, format_digest, get_notifier


def test_console_fallback_when_telegram_env_missing(monkeypatch, capsys) -> None:
    monkeypatch.delenv("TELEGRAM_BOT_TOKEN", raising=False)
    monkeypatch.delenv("TELEGRAM_CHAT_ID", raising=False)
    notifier = get_notifier()
    assert isinstance(notifier, ConsoleNotifier)
    notifier.send("hello")
    assert "hello" in capsys.readouterr().out


def test_format_digest_empty() -> None:
    assert "no matches" in format_digest([])


def test_format_digest_rows() -> None:
    text = format_digest(
        [
            {
                "score": 82,
                "title": "Backend Engineer",
                "company": "Northwind Labs",
                "url": "https://jobs.example.com/be",
            }
        ]
    )
    assert "82" in text
    assert "Northwind Labs" in text
