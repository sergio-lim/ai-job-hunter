from __future__ import annotations

import requests

from jobhunter.models import Job
from jobhunter.verify import check_url, verify_jobs


class DummyResponse:
    def __init__(self, status_code: int) -> None:
        self.status_code = status_code

    def close(self) -> None:
        return None


def test_ok_on_head_200(monkeypatch) -> None:
    monkeypatch.setattr(
        "jobhunter.verify.requests.head",
        lambda *args, **kwargs: DummyResponse(200),
    )
    label, code = check_url("https://jobs.example.com/alive")
    assert label == "ok"
    assert code == 200


def test_dead_on_404(monkeypatch) -> None:
    monkeypatch.setattr(
        "jobhunter.verify.requests.head",
        lambda *args, **kwargs: DummyResponse(404),
    )
    label, code = check_url("https://jobs.example.com/missing")
    assert label == "dead"
    assert code == 404


def test_dead_on_410(monkeypatch) -> None:
    monkeypatch.setattr(
        "jobhunter.verify.requests.head",
        lambda *args, **kwargs: DummyResponse(410),
    )
    assert check_url("https://jobs.example.com/gone") == ("dead", 410)


def test_get_fallback_when_head_rejects(monkeypatch) -> None:
    monkeypatch.setattr(
        "jobhunter.verify.requests.head",
        lambda *args, **kwargs: DummyResponse(405),
    )
    monkeypatch.setattr(
        "jobhunter.verify.requests.get",
        lambda *args, **kwargs: DummyResponse(301),
    )
    assert check_url("https://jobs.example.com/redirect") == ("ok", 301)


def test_timeout_is_error(monkeypatch) -> None:
    def boom(*args, **kwargs):
        raise requests.Timeout("slow")

    monkeypatch.setattr("jobhunter.verify.requests.head", boom)
    monkeypatch.setattr("jobhunter.verify.requests.get", boom)
    label, code = check_url("https://jobs.example.com/slow")
    assert label == "error"
    assert code is None


def test_verify_jobs_drops_dead_keeps_ok(monkeypatch) -> None:
    mapping = {
        "https://jobs.example.com/ok": DummyResponse(200),
        "https://jobs.example.com/gone": DummyResponse(404),
    }

    def fake_head(url, **kwargs):
        return mapping[url]

    monkeypatch.setattr("jobhunter.verify.requests.head", fake_head)
    jobs = [
        Job(id="1", title="A", company="Acme", url="https://jobs.example.com/ok"),
        Job(id="2", title="B", company="Acme", url="https://jobs.example.com/gone"),
    ]
    kept = verify_jobs(jobs)
    assert [job.id for job in kept] == ["1"]
    assert kept[0].status == "ok"


def test_skip_http_marks_ok_without_network(sample_jobs: list[Job]) -> None:
    kept = verify_jobs(sample_jobs, skip_http=True)
    assert len(kept) == len(sample_jobs)
    assert all(job.status == "ok" for job in kept)
