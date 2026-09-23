from __future__ import annotations

from jobhunter.models import Job
from jobhunter.score import Profile, score_job, score_jobs


def test_strong_backend_match(profile: Profile, sample_jobs: list[Job]) -> None:
    job = next(item for item in sample_jobs if item.id == "sample:1001")
    result = score_job(job, profile)
    assert result.score >= 70
    assert any("role match" in reason for reason in result.reasons)
    assert any("remote" in reason for reason in result.reasons)


def test_excluded_keyword_collapses_score(profile: Profile, sample_jobs: list[Job]) -> None:
    job = next(item for item in sample_jobs if item.id == "sample:1009")
    result = score_job(job, profile)
    assert result.score == 0
    assert any("excluded" in reason for reason in result.reasons)


def test_remote_only_caps_onsite_roles(profile: Profile, sample_jobs: list[Job]) -> None:
    job = next(item for item in sample_jobs if item.id == "sample:1008")
    result = score_job(job, profile)
    assert result.score <= 20
    assert any("not remote" in reason for reason in result.reasons)


def test_skill_hits_raise_score() -> None:
    profile = Profile(skills=["python", "postgres"], roles=[], remote_only=False)
    weak = Job(
        id="w",
        title="Office Coordinator",
        company="Acme",
        url="https://jobs.example.com/w",
        location="Remote",
        description="Calendar and snacks.",
    )
    strong = Job(
        id="s",
        title="Office Coordinator",
        company="Acme",
        url="https://jobs.example.com/s",
        location="Remote",
        description="Python services on Postgres.",
        tags=["python", "postgres"],
    )
    assert score_job(strong, profile).score > score_job(weak, profile).score


def test_score_jobs_sorts_descending(profile: Profile, sample_jobs: list[Job]) -> None:
    ranked = score_jobs(sample_jobs, profile)
    scores = [item.score for item in ranked]
    assert scores == sorted(scores, reverse=True)
    assert ranked[0].job.id != "sample:1009"
