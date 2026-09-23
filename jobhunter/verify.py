from __future__ import annotations

import logging

import requests

from jobhunter.models import Job

log = logging.getLogger(__name__)

DEAD_STATUSES = frozenset({404, 410})
OK_STATUSES = frozenset(range(200, 400))
DEFAULT_TIMEOUT = 12
USER_AGENT = "ai-job-hunter/0.1 (+https://github.com/)"


def check_url(url: str, timeout: float = DEFAULT_TIMEOUT) -> tuple[str, int | None]:
    """Return (status_label, http_code). Follows redirects. HEAD first, then GET."""

    headers = {"User-Agent": USER_AGENT, "Accept": "*/*"}
    try:
        response = requests.head(
            url,
            headers=headers,
            timeout=timeout,
            allow_redirects=True,
        )
        code = response.status_code
        if code in DEAD_STATUSES:
            return "dead", code
        if code in OK_STATUSES:
            return "ok", code
        # Some boards reject HEAD; fall through to GET.
        if code not in {403, 405, 501}:
            return "error", code
    except requests.RequestException as exc:
        log.debug("HEAD %s failed (%s); trying GET", url, exc)

    try:
        response = requests.get(
            url,
            headers=headers,
            timeout=timeout,
            allow_redirects=True,
            stream=True,
        )
        response.close()
        code = response.status_code
        if code in DEAD_STATUSES:
            return "dead", code
        if code in OK_STATUSES:
            return "ok", code
        return "error", code
    except requests.RequestException as exc:
        log.warning("verify failed for %s: %s", url, exc)
        return "error", None


def verify_jobs(
    jobs: list[Job],
    timeout: float = DEFAULT_TIMEOUT,
    skip_http: bool = False,
) -> list[Job]:
    """Mark each job and drop listings that resolve to 404 or 410."""

    kept: list[Job] = []
    for job in jobs:
        if skip_http:
            job.status = job.status if job.status != "unverified" else "ok"
            kept.append(job)
            continue
        label, code = check_url(job.url, timeout=timeout)
        job.status = label
        if label == "dead":
            log.info("discard %s (%s)", job.url, code)
            continue
        kept.append(job)
    return kept
