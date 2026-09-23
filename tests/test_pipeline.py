from __future__ import annotations

import json
from pathlib import Path

from jobhunter.models import Job
from jobhunter.pipeline import run_pipeline
from jobhunter.score import Profile, score_job


def test_excluded_company_scores_zero_and_is_dropped_from_pipeline(tmp_path: Path) -> None:
    profile = Profile(
        roles=["backend engineer"],
        skills=["python"],
        remote_only=False,
        excluded_companies=["Acme Corp"],
    )
    excluded = Job(
        id="sample:excluded",
        title="Backend Engineer",
        company="ACME Corp Holdings",
        url="https://jobs.example.com/acme-corp/backend-engineer",
        location="Remote — Worldwide",
        tags=["python", "remote"],
        source="sample",
        description="Python APIs and worker pipelines. Fully remote.",
        status="ok",
    )
    kept = Job(
        id="sample:kept",
        title="Backend Engineer",
        company="Northwind Labs",
        url="https://jobs.example.com/northwind-labs/backend-engineer",
        location="Remote — Worldwide",
        tags=["python", "remote"],
        source="sample",
        description="Python APIs and worker pipelines. Fully remote.",
        status="ok",
    )

    scored = score_job(excluded, profile)
    assert scored.score == 0
    assert scored.reasons == ["excluded company: Acme Corp"]

    samples_path = tmp_path / "jobs.json"
    samples_path.write_text(json.dumps([excluded.to_dict(), kept.to_dict()]), encoding="utf-8")
    profile_path = tmp_path / "profile.json"
    profile_path.write_text(
        json.dumps(
            {
                "roles": ["backend engineer"],
                "skills": ["python"],
                "remote_only": False,
                "excluded_companies": ["Acme Corp"],
            }
        ),
        encoding="utf-8",
    )

    results = run_pipeline(
        demo=True,
        min_score=0,
        dry_run=True,
        notify=False,
        profile_path=profile_path,
        samples_path=samples_path,
    )
    ids = [item.job.id for item in results]
    companies = [item.job.company.lower() for item in results]
    assert "sample:excluded" not in ids
    assert all("acme" not in company for company in companies)
    assert "sample:kept" in ids
