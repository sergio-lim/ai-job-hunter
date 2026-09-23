from __future__ import annotations

import logging
from pathlib import Path

from jobhunter.dedupe import SeenStore, dedupe
from jobhunter.models import Job
from jobhunter.notify import format_digest, get_notifier
from jobhunter.score import Profile, ScoredJob, default_profile_path, score_jobs
from jobhunter.sources import fetch, load_sample_jobs
from jobhunter.verify import verify_jobs

log = logging.getLogger(__name__)


def load_profile(path: Path | None) -> Profile:
    return Profile.load(path or default_profile_path())


def collect(demo: bool, limit: int | None, samples: Path | None = None) -> list[Job]:
    if demo:
        jobs = load_sample_jobs(samples)
        log.info("demo: loaded %s sample job(s)", len(jobs))
        return jobs
    return fetch(limit or 20)


def run_pipeline(
    *,
    demo: bool = True,
    limit: int = 20,
    min_score: int = 0,
    dry_run: bool = False,
    profile_path: Path | None = None,
    seen_path: Path | None = None,
    samples_path: Path | None = None,
    notify: bool = True,
) -> list[ScoredJob]:
    profile = load_profile(profile_path)
    jobs = collect(demo=demo, limit=None if demo else limit, samples=samples_path)

    store = None
    if seen_path is not None:
        store = SeenStore(seen_path)
    jobs = dedupe(jobs, store=store)
    jobs = verify_jobs(jobs, skip_http=demo)

    scored = [item for item in score_jobs(jobs, profile) if item.score >= min_score]
    if limit:
        scored = scored[:limit]

    if store is not None and not dry_run:
        for item in scored:
            store.remember(item.job)
        store.save()

    if notify and not dry_run:
        notifier = get_notifier()
        payload = [item.to_dict() for item in scored]
        heading = "Job hunt digest (demo)" if demo else "Job hunt digest"
        notifier.send(format_digest(payload, heading=heading))

    return scored
