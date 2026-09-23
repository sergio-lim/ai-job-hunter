from __future__ import annotations

import json

from jobhunter.cli import main


def test_demo_table(capsys) -> None:
    code = main(["run", "--demo", "--min-score", "0", "--limit", "10", "--dry-run"])
    assert code == 0
    out = capsys.readouterr().out
    assert "SCORE" in out
    assert "Northwind Labs" in out
    assert "TITLE" in out


def test_demo_json(capsys) -> None:
    code = main(["run", "--demo", "--json", "--min-score", "0", "--limit", "3", "--dry-run"])
    assert code == 0
    payload = json.loads(capsys.readouterr().out)
    assert isinstance(payload, list)
    assert 1 <= len(payload) <= 3
    first = payload[0]
    assert "title" in first
    assert "score" in first
    assert "reasons" in first
    assert "url" in first


def test_demo_min_score_filters(capsys) -> None:
    code = main(["run", "--demo", "--json", "--min-score", "60", "--limit", "20", "--dry-run"])
    assert code == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload
    assert all(row["score"] >= 60 for row in payload)
    titles = " ".join(row["title"] for row in payload).lower()
    assert "intern" not in titles


def test_classify_text(capsys) -> None:
    code = main(
        [
            "classify",
            "--text",
            "Thanks for applying! We have received your application.",
        ]
    )
    assert code == 0
    out = capsys.readouterr().out
    assert "simple_ack" in out
