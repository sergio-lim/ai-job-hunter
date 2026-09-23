from __future__ import annotations

import json
import logging
import os
import re
from pathlib import Path
from typing import Protocol
from urllib.parse import urljoin

import requests

from jobhunter.models import Job

log = logging.getLogger(__name__)

USER_AGENT = "ai-job-hunter/0.1 (+https://github.com/)"
DEFAULT_TIMEOUT = 20
ARBEITNOW_URL = "https://www.arbeitnow.com/api/job-board-api"
REMOTEOK_URL = "https://remoteok.com/api"
GREENHOUSE_BOARD_URL = "https://job-boards.greenhouse.io/{board}"
GREENHOUSE_API_URL = "https://boards-api.greenhouse.io/v1/boards/{board}/jobs"
DEFAULT_GREENHOUSE_BOARDS = ("gitlab",)

_JOB_HREF = re.compile(
    r'href="(?P<href>(?:https://job-boards\.greenhouse\.io)?/[^"]+/jobs/\d+)"',
    re.IGNORECASE,
)
_TITLE_NEAR_HREF = re.compile(
    r'href="(?P<href>(?:https://job-boards\.greenhouse\.io)?/[^"]+/jobs/\d+)"[^>]*>(?P<title>[^<]{3,160})',
    re.IGNORECASE,
)


class Source(Protocol):
    name: str

    def fetch(self, limit: int) -> list[Job]:
        """Return up to `limit` jobs. Raise on hard failure."""


def _session() -> requests.Session:
    session = requests.Session()
    session.headers.update({"User-Agent": USER_AGENT, "Accept": "application/json, text/html"})
    return session


def _text(value: object) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _tags(value: object) -> list[str]:
    if not value:
        return []
    if isinstance(value, str):
        return [part.strip() for part in re.split(r"[,|/]", value) if part.strip()]
    if isinstance(value, list):
        out: list[str] = []
        for item in value:
            if isinstance(item, dict):
                name = item.get("name") or item.get("slug") or ""
                if name:
                    out.append(str(name))
            elif item:
                out.append(str(item))
        return out
    return []


class ArbeitnowSource:
    name = "arbeitnow"

    def fetch(self, limit: int) -> list[Job]:
        jobs: list[Job] = []
        page = 1
        session = _session()
        while len(jobs) < limit:
            response = session.get(
                ARBEITNOW_URL,
                params={"page": page},
                timeout=DEFAULT_TIMEOUT,
            )
            response.raise_for_status()
            payload = response.json()
            rows = payload.get("data") if isinstance(payload, dict) else payload
            if not rows:
                break
            added = 0
            for row in rows:
                if len(jobs) >= limit:
                    break
                job_id = _text(row.get("slug") or row.get("id"))
                url = _text(row.get("url"))
                if not job_id or not url:
                    continue
                full_id = f"{self.name}:{job_id}"
                if any(item.id == full_id for item in jobs):
                    continue
                jobs.append(
                    Job(
                        id=full_id,
                        title=_text(row.get("title")),
                        company=_text(row.get("company_name") or row.get("company")),
                        url=url,
                        location=_text(row.get("location")),
                        tags=_tags(row.get("tags")),
                        source=self.name,
                        description=_text(row.get("description")),
                    )
                )
                added += 1
            if added == 0:
                break
            page += 1
            if page > 5:
                break
        return jobs[:limit]


class RemoteOKSource:
    name = "remoteok"

    def fetch(self, limit: int) -> list[Job]:
        session = _session()
        response = session.get(REMOTEOK_URL, timeout=DEFAULT_TIMEOUT)
        response.raise_for_status()
        payload = response.json()
        jobs: list[Job] = []
        if not isinstance(payload, list):
            return jobs
        for row in payload:
            if not isinstance(row, dict):
                continue
            job_id = row.get("id")
            title = _text(row.get("position") or row.get("title"))
            if not job_id or not title:
                continue
            url = _text(row.get("url") or row.get("apply_url"))
            if not url:
                continue
            jobs.append(
                Job(
                    id=f"{self.name}:{job_id}",
                    title=title,
                    company=_text(row.get("company")),
                    url=url,
                    location=_text(row.get("location")),
                    tags=_tags(row.get("tags")),
                    source=self.name,
                    description=_text(row.get("description")),
                )
            )
            if len(jobs) >= limit:
                break
        return jobs


class GreenhouseSource:
    """Public Greenhouse boards. HTML list first, official JSON API as fallback."""

    name = "greenhouse"

    def __init__(self, boards: list[str] | None = None) -> None:
        if boards is None:
            raw = os.environ.get("GREENHOUSE_BOARDS", "")
            boards = [part.strip() for part in raw.split(",") if part.strip()]
        self.boards = boards or list(DEFAULT_GREENHOUSE_BOARDS)

    def fetch(self, limit: int) -> list[Job]:
        jobs: list[Job] = []
        session = _session()
        per_board = max(1, limit)
        for board in self.boards:
            if len(jobs) >= limit:
                break
            remaining = limit - len(jobs)
            try:
                found = self._fetch_board(session, board, min(per_board, remaining))
            except Exception as exc:  # noqa: BLE001 — one board must not kill the source
                log.warning("greenhouse board %s failed: %s", board, exc)
                continue
            jobs.extend(found)
        return jobs[:limit]

    def _fetch_board(self, session: requests.Session, board: str, limit: int) -> list[Job]:
        html_jobs = self._from_html(session, board, limit)
        if html_jobs:
            return html_jobs
        return self._from_api(session, board, limit)

    def _from_html(self, session: requests.Session, board: str, limit: int) -> list[Job]:
        url = GREENHOUSE_BOARD_URL.format(board=board)
        response = session.get(url, timeout=DEFAULT_TIMEOUT)
        response.raise_for_status()
        html = response.text
        jobs: list[Job] = []
        seen: set[str] = set()
        for match in _TITLE_NEAR_HREF.finditer(html):
            href = match.group("href")
            title = re.sub(r"\s+", " ", match.group("title")).strip()
            abs_url = href if href.startswith("http") else urljoin(url, href)
            if abs_url in seen or not title:
                continue
            seen.add(abs_url)
            job_id = abs_url.rstrip("/").split("/")[-1]
            jobs.append(
                Job(
                    id=f"{self.name}:{board}:{job_id}",
                    title=title,
                    company=board,
                    url=abs_url,
                    location="",
                    tags=[],
                    source=self.name,
                    description="",
                )
            )
            if len(jobs) >= limit:
                break
        if jobs:
            return jobs
        for match in _JOB_HREF.finditer(html):
            href = match.group("href")
            abs_url = href if href.startswith("http") else urljoin(url, href)
            if abs_url in seen:
                continue
            seen.add(abs_url)
            job_id = abs_url.rstrip("/").split("/")[-1]
            jobs.append(
                Job(
                    id=f"{self.name}:{board}:{job_id}",
                    title=f"Role {job_id}",
                    company=board,
                    url=abs_url,
                    source=self.name,
                )
            )
            if len(jobs) >= limit:
                break
        return jobs

    def _from_api(self, session: requests.Session, board: str, limit: int) -> list[Job]:
        url = GREENHOUSE_API_URL.format(board=board)
        response = session.get(url, params={"content": "true"}, timeout=DEFAULT_TIMEOUT)
        response.raise_for_status()
        payload = response.json()
        rows = payload.get("jobs") if isinstance(payload, dict) else []
        jobs: list[Job] = []
        for row in rows:
            if len(jobs) >= limit:
                break
            job_id = row.get("id")
            abs_url = _text(row.get("absolute_url"))
            title = _text(row.get("title"))
            if not job_id or not abs_url or not title:
                continue
            location = ""
            loc = row.get("location")
            if isinstance(loc, dict):
                location = _text(loc.get("name"))
            jobs.append(
                Job(
                    id=f"{self.name}:{board}:{job_id}",
                    title=title,
                    company=_text(row.get("company_name")) or board,
                    url=abs_url,
                    location=location,
                    tags=[],
                    source=self.name,
                    description=_text(row.get("content")),
                )
            )
        return jobs


ALL_SOURCES: dict[str, Source] = {
    "arbeitnow": ArbeitnowSource(),
    "remoteok": RemoteOKSource(),
    "greenhouse": GreenhouseSource(),
}


def fetch(limit: int, names: list[str] | None = None) -> list[Job]:
    """Collect jobs from every requested source. A failing source is skipped."""

    selected = names or list(ALL_SOURCES)
    collected: list[Job] = []
    for name in selected:
        source = ALL_SOURCES.get(name)
        if source is None:
            log.warning("unknown source %s — skipping", name)
            continue
        try:
            found = source.fetch(limit)
            log.info("source %s returned %s job(s)", name, len(found))
            collected.extend(found)
        except Exception as exc:  # noqa: BLE001 — isolate source failures
            log.warning("source %s failed: %s", name, exc)
    return collected


def load_sample_jobs(path: Path | None = None) -> list[Job]:
    target = path or default_samples_path()
    with target.open(encoding="utf-8") as handle:
        rows = json.load(handle)
    return [Job.from_dict(row) for row in rows]


def default_samples_path() -> Path:
    bundled = Path(__file__).resolve().parent.parent / "data" / "samples" / "jobs.json"
    if bundled.is_file():
        return bundled
    return Path.cwd() / "data" / "samples" / "jobs.json"
