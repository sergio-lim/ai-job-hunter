from __future__ import annotations

import json
import logging
import os
import re
from dataclasses import dataclass

import requests

log = logging.getLogger(__name__)

SIMPLE_ACK = "simple_ack"
NEEDS_JUDGMENT = "needs_judgment"
LABELS = (SIMPLE_ACK, NEEDS_JUDGMENT)

# Deterministic baseline: obvious auto-replies vs anything that needs a human.
_SIMPLE_PATTERNS = (
    re.compile(r"\bthanks for (your )?(applying|application|interest)\b", re.I),
    re.compile(r"\bthank you for (your )?(applying|application|interest)\b", re.I),
    re.compile(r"\bwe (have )?received your (application|resume|cv)\b", re.I),
    re.compile(r"\bapplication (has been )?received\b", re.I),
    re.compile(r"\bwe will (review|be in touch)\b", re.I),
    re.compile(r"\bno (further )?action (is )?needed\b", re.I),
    re.compile(r"\bcurrently reviewing (your )?application\b", re.I),
    re.compile(r"\bthis is an automated (message|reply|response)\b", re.I),
)

_JUDGMENT_PATTERNS = (
    re.compile(r"\b(interview|phone screen|take[- ]home|assignment)\b", re.I),
    re.compile(r"\b(available|availability|schedule a call|book a time)\b", re.I),
    re.compile(r"\b(offer|compensation|salary|rate|start date)\b", re.I),
    re.compile(r"\b(when can you|are you open|would you be)\b", re.I),
    re.compile(r"\b(please (reply|respond|confirm|send)|can you share)\b", re.I),
    re.compile(r"\b(next steps|move forward|happy to chat)\b", re.I),
)


@dataclass
class Classification:
    label: str
    method: str
    reason: str

    def to_dict(self) -> dict[str, str]:
        return {"label": self.label, "method": self.method, "reason": self.reason}


def classify_regex(text: str) -> Classification:
    blob = (text or "").strip()
    if not blob:
        return Classification(NEEDS_JUDGMENT, "regex", "empty message")

    for pattern in _JUDGMENT_PATTERNS:
        if pattern.search(blob):
            return Classification(NEEDS_JUDGMENT, "regex", f"matched {pattern.pattern}")

    for pattern in _SIMPLE_PATTERNS:
        if pattern.search(blob):
            return Classification(SIMPLE_ACK, "regex", f"matched {pattern.pattern}")

    return Classification(NEEDS_JUDGMENT, "regex", "no simple-ack pattern")


def classify_llm(text: str) -> Classification:
    key = os.environ.get("LLM_API_KEY")
    if not key:
        raise RuntimeError("LLM_API_KEY is not set")
    base = os.environ.get("LLM_BASE_URL", "https://api.openai.com/v1").rstrip("/")
    model = os.environ.get("LLM_MODEL", "gpt-4o-mini")
    payload = {
        "model": model,
        "temperature": 0,
        "max_tokens": 8,
        "messages": [
            {
                "role": "system",
                "content": (
                    "Classify a recruiter email as exactly one label: "
                    "simple_ack or needs_judgment. Reply with the label only."
                ),
            },
            {"role": "user", "content": text},
        ],
    }
    response = requests.post(
        f"{base}/chat/completions",
        headers={
            "Authorization": f"Bearer {key}",
            "Content-Type": "application/json",
        },
        json=payload,
        timeout=30,
    )
    response.raise_for_status()
    body = response.json()
    content = body["choices"][0]["message"]["content"].strip().lower()
    if "simple" in content:
        label = SIMPLE_ACK
    else:
        label = NEEDS_JUDGMENT
    return Classification(label, "llm", content)


def classify_reply(text: str, use_llm: bool = False) -> Classification:
    """Regex baseline, with an optional OpenAI-compatible hook.

    `--llm` only calls the network when LLM_API_KEY is present. Otherwise it
    stays on the deterministic classifier and says so.
    """

    if use_llm:
        if not os.environ.get("LLM_API_KEY"):
            result = classify_regex(text)
            result.reason = "LLM_API_KEY missing; used regex"
            log.info("no LLM credential in the environment; using regex baseline")
            return result
        try:
            return classify_llm(text)
        except Exception as exc:  # noqa: BLE001 — always fall back
            log.warning("llm classify failed (%s); using regex", exc)
            result = classify_regex(text)
            result.reason = f"llm failed; regex: {result.reason}"
            return result
    return classify_regex(text)


def classify_file(path: str, use_llm: bool = False) -> list[dict[str, object]]:
    with open(path, encoding="utf-8") as handle:
        rows = json.load(handle)
    out: list[dict[str, object]] = []
    for row in rows:
        text = row.get("text", "") if isinstance(row, dict) else str(row)
        result = classify_reply(text, use_llm=use_llm)
        item = result.to_dict()
        item["text"] = text
        if isinstance(row, dict) and "id" in row:
            item["id"] = row["id"]
        out.append(item)
    return out
