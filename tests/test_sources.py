from __future__ import annotations

import requests

from jobhunter.models import Job
from jobhunter.sources import (
    ArbeitnowSource,
    GreenhouseSource,
    RemoteOKSource,
    fetch,
)


class FakeResponse:
    def __init__(self, payload=None, text="", status_code=200) -> None:
        self._payload = payload
        self.text = text
        self.status_code = status_code

    def json(self):
        return self._payload

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise requests.HTTPError(f"status {self.status_code}")


def test_arbeitnow_maps_fields(monkeypatch) -> None:
    payload = {
        "data": [
            {
                "slug": "py-1",
                "title": "Python Engineer",
                "company_name": "Northwind Labs",
                "url": "https://www.arbeitnow.com/jobs/py-1",
                "location": "Remote",
                "tags": ["python"],
                "description": "APIs",
            }
        ]
    }

    def fake_get(self, url, **kwargs):
        return FakeResponse(payload=payload)

    monkeypatch.setattr(requests.Session, "get", fake_get)
    jobs = ArbeitnowSource().fetch(5)
    assert len(jobs) == 1
    assert jobs[0].id == "arbeitnow:py-1"
    assert jobs[0].company == "Northwind Labs"
    assert jobs[0].source == "arbeitnow"


def test_remoteok_skips_legal_banner(monkeypatch) -> None:
    payload = [
        {"legal": "notice"},
        {
            "id": 99,
            "position": "Platform Engineer",
            "company": "Helios Analytics",
            "url": "https://remoteok.com/remote-jobs/99",
            "location": "Worldwide",
            "tags": ["kubernetes"],
            "description": "Platform work",
        },
    ]

    def fake_get(self, url, **kwargs):
        return FakeResponse(payload=payload)

    monkeypatch.setattr(requests.Session, "get", fake_get)
    jobs = RemoteOKSource().fetch(5)
    assert [job.id for job in jobs] == ["remoteok:99"]


def test_greenhouse_parses_public_board_html(monkeypatch) -> None:
    html = """
    <section>
      <a href="/acme/jobs/4242">Backend Engineer</a>
      <a href="https://job-boards.greenhouse.io/acme/jobs/4243">Data Engineer</a>
    </section>
    """

    def fake_get(self, url, **kwargs):
        return FakeResponse(text=html)

    monkeypatch.setattr(requests.Session, "get", fake_get)
    jobs = GreenhouseSource(boards=["acme"]).fetch(10)
    assert len(jobs) == 2
    assert jobs[0].source == "greenhouse"
    assert jobs[0].url.endswith("/jobs/4242")
    assert jobs[1].title == "Data Engineer"


def test_fetch_continues_when_one_source_fails(monkeypatch) -> None:
    def boom(self, limit: int) -> list[Job]:
        raise RuntimeError("down")

    def ok(self, limit: int) -> list[Job]:
        return [
            Job(
                id="remoteok:1",
                title="Backend Engineer",
                company="Maple Stack",
                url="https://jobs.example.com/ok",
                source="remoteok",
            )
        ]

    monkeypatch.setattr(ArbeitnowSource, "fetch", boom)
    monkeypatch.setattr(RemoteOKSource, "fetch", ok)
    monkeypatch.setattr(GreenhouseSource, "fetch", boom)
    jobs = fetch(3)
    assert len(jobs) == 1
    assert jobs[0].source == "remoteok"
