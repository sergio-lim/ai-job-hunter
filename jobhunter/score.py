from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from jobhunter.models import Job

ROLE_POINTS = 30
SKILL_POINTS_EACH = 8
SKILL_POINTS_CAP = 40
LOCATION_POINTS = 15
KEYWORD_POINTS_EACH = 5
KEYWORD_POINTS_CAP = 10
REMOTE_BONUS = 5
EXCLUDED_PENALTY = 50

REMOTE_MARKERS = (
    "remote",
    "worldwide",
    "anywhere",
    "distributed",
    "work from home",
    "wfh",
)


@dataclass
class Profile:
    skills: list[str] = field(default_factory=list)
    roles: list[str] = field(default_factory=list)
    locations: list[str] = field(default_factory=list)
    remote_only: bool = False
    keywords: list[str] = field(default_factory=list)
    excluded_keywords: list[str] = field(default_factory=list)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Profile:
        def as_list(key: str) -> list[str]:
            values = data.get(key) or []
            if isinstance(values, str):
                return [values]
            return [str(item) for item in values]

        return cls(
            skills=as_list("skills"),
            roles=as_list("roles"),
            locations=as_list("locations"),
            remote_only=bool(data.get("remote_only", False)),
            keywords=as_list("keywords"),
            excluded_keywords=as_list("excluded_keywords"),
        )

    @classmethod
    def load(cls, path: Path) -> Profile:
        with path.open(encoding="utf-8") as handle:
            return cls.from_dict(json.load(handle))


@dataclass
class ScoredJob:
    job: Job
    score: int
    reasons: list[str]

    def to_dict(self) -> dict[str, Any]:
        payload = self.job.to_dict()
        payload["score"] = self.score
        payload["reasons"] = list(self.reasons)
        return payload


def _haystack(job: Job) -> str:
    parts = [job.title, job.company, job.location, job.description, " ".join(job.tags)]
    return " ".join(parts).lower()


def _contains(term: str, text: str) -> bool:
    needle = term.strip().lower()
    if not needle:
        return False
    if re.search(r"\s", needle):
        return needle in text
    return re.search(rf"\b{re.escape(needle)}\b", text) is not None


def is_remote(job: Job) -> bool:
    text = f"{job.location} {' '.join(job.tags)} {job.title} {job.description}".lower()
    return any(marker in text for marker in REMOTE_MARKERS)


def score_job(job: Job, profile: Profile) -> ScoredJob:
    """Score a job 0-100 against a profile. Rules are deterministic."""

    text = _haystack(job)
    title = job.title.lower()
    reasons: list[str] = []
    points = 0

    excluded_hits = [term for term in profile.excluded_keywords if _contains(term, text)]
    if excluded_hits:
        points -= EXCLUDED_PENALTY
        reasons.append(f"excluded keyword: {excluded_hits[0]}")

    matched_roles = [role for role in profile.roles if _contains(role, title)]
    if matched_roles:
        points += ROLE_POINTS
        reasons.append(f"role match: {matched_roles[0]}")

    skill_hits = [skill for skill in profile.skills if _contains(skill, text)]
    if skill_hits:
        skill_points = min(SKILL_POINTS_CAP, SKILL_POINTS_EACH * len(skill_hits))
        points += skill_points
        reasons.append(f"skills: {', '.join(skill_hits[:5])} (+{skill_points})")

    remote = is_remote(job)
    location_hits = [loc for loc in profile.locations if _contains(loc, text)]
    if profile.remote_only and not remote and not location_hits:
        reasons.append("not remote and location does not match")
        return ScoredJob(job=job, score=max(0, min(points, 20)), reasons=reasons)
    if remote:
        points += LOCATION_POINTS + REMOTE_BONUS
        reasons.append("remote-friendly")
    elif location_hits:
        points += LOCATION_POINTS
        reasons.append(f"location match: {location_hits[0]}")

    keyword_hits = [kw for kw in profile.keywords if _contains(kw, text)]
    if keyword_hits:
        kw_points = min(KEYWORD_POINTS_CAP, KEYWORD_POINTS_EACH * len(keyword_hits))
        points += kw_points
        reasons.append(f"keywords: {', '.join(keyword_hits[:4])}")

    if not reasons:
        reasons.append("no profile overlap")

    score = max(0, min(100, points))
    return ScoredJob(job=job, score=score, reasons=reasons)


def score_jobs(jobs: list[Job], profile: Profile) -> list[ScoredJob]:
    scored = [score_job(job, profile) for job in jobs]
    scored.sort(key=lambda item: (-item.score, item.job.title.lower()))
    return scored


def default_profile_path() -> Path:
    bundled = Path(__file__).resolve().parent.parent / "profile.example.json"
    if bundled.is_file():
        return bundled
    return Path.cwd() / "profile.example.json"
