from __future__ import annotations

from jobhunter.dedupe import SeenStore, dedupe, identity_hash, normalize_url
from jobhunter.models import Job


def _job(job_id: str, title: str, company: str, url: str) -> Job:
    return Job(id=job_id, title=title, company=company, url=url, source="test")


def test_normalize_url_strips_tracking_and_slash() -> None:
    left = "https://WWW.Example.com/jobs/abc/?utm_source=board&utm_campaign=x"
    right = "https://example.com/jobs/abc"
    assert normalize_url(left) == normalize_url(right)


def test_dedupe_same_url_different_ids() -> None:
    jobs = [
        _job("a", "Backend Engineer", "Northwind Labs", "https://jobs.example.com/role"),
        _job("b", "Backend Engineer (copy)", "Other Co", "https://jobs.example.com/role/"),
    ]
    kept = dedupe(jobs)
    assert [job.id for job in kept] == ["a"]


def test_dedupe_similar_title_company() -> None:
    jobs = [
        _job("a", "Senior Backend Engineer", "Northwind Labs", "https://jobs.example.com/one"),
        _job("b", "Senior Backend Engineer", "Northwind Labs", "https://jobs.example.com/two"),
    ]
    kept = dedupe(jobs)
    assert [job.id for job in kept] == ["a"]
    assert identity_hash("Senior Backend Engineer", "Northwind Labs") == identity_hash(
        "senior  backend engineer", "northwind labs"
    )


def test_seen_store_persists(tmp_path) -> None:
    path = tmp_path / "seen.json"
    store = SeenStore(path)
    first = _job("sample:1001", "Data Engineer", "Maple Stack", "https://jobs.example.com/de")
    store.remember(first)
    store.save()

    again = SeenStore(path)
    jobs = [
        first,
        _job("sample:1099", "QA Automation Engineer", "Brightwell Testing", "https://jobs.example.com/qa"),
    ]
    kept = dedupe(jobs, store=again)
    assert [job.id for job in kept] == ["sample:1099"]
