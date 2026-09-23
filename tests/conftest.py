from __future__ import annotations

import json
from pathlib import Path

import pytest

from jobhunter.models import Job
from jobhunter.score import Profile

ROOT = Path(__file__).resolve().parent.parent
SAMPLES = ROOT / "data" / "samples" / "jobs.json"
REPLIES = ROOT / "data" / "samples" / "replies.samples.json"
PROFILE = ROOT / "profile.example.json"


@pytest.fixture
def sample_jobs() -> list[Job]:
    rows = json.loads(SAMPLES.read_text(encoding="utf-8"))
    return [Job.from_dict(row) for row in rows]


@pytest.fixture
def profile() -> Profile:
    return Profile.load(PROFILE)


@pytest.fixture
def replies() -> list[dict]:
    return json.loads(REPLIES.read_text(encoding="utf-8"))
