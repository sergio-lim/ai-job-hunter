from __future__ import annotations

from jobhunter.classify import (
    NEEDS_JUDGMENT,
    SIMPLE_ACK,
    classify_regex,
    classify_reply,
)


def test_samples_match_expected_labels(replies: list[dict]) -> None:
    for row in replies:
        result = classify_regex(row["text"])
        assert result.label == row["expected"], row["id"]
        assert result.method == "regex"


def test_empty_needs_judgment() -> None:
    assert classify_regex("").label == NEEDS_JUDGMENT


def test_llm_flag_without_credential_stays_on_regex(monkeypatch) -> None:
    monkeypatch.delenv("LLM_API_KEY", raising=False)
    text = "Thanks for applying! We have received your application and will review it shortly."
    result = classify_reply(text, use_llm=True)
    assert result.label == SIMPLE_ACK
    assert result.method == "regex"
    assert "LLM_API_KEY missing" in result.reason


def test_llm_failure_falls_back(monkeypatch) -> None:
    monkeypatch.setenv("LLM_API_KEY", "sk-test-not-a-real-credential")

    def boom(_text: str):
        raise RuntimeError("network down")

    monkeypatch.setattr("jobhunter.classify.classify_llm", boom)
    result = classify_reply("Thanks for applying, we received your application.", use_llm=True)
    assert result.label == SIMPLE_ACK
    assert result.method == "regex"
    assert "llm failed" in result.reason


def test_judgment_beats_ack_when_interview_is_mentioned() -> None:
    text = "Thanks for applying. Are you available for an interview on Monday?"
    assert classify_regex(text).label == NEEDS_JUDGMENT
