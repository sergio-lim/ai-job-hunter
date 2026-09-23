from __future__ import annotations

import hashlib
import json
import logging
import re
from difflib import SequenceMatcher
from pathlib import Path
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from jobhunter.models import Job

log = logging.getLogger(__name__)

TRACKING_PARAMS = frozenset(
    {
        "utm_source",
        "utm_medium",
        "utm_campaign",
        "utm_term",
        "utm_content",
        "gclid",
        "fbclid",
        "ref",
        "source",
    }
)
DEFAULT_SIMILARITY = 0.92


def normalize_url(url: str) -> str:
    raw = (url or "").strip()
    if not raw:
        return ""
    parts = urlsplit(raw)
    scheme = (parts.scheme or "https").lower()
    host = parts.netloc.lower()
    if host.startswith("www."):
        host = host[4:]
    path = parts.path.rstrip("/") or "/"
    query_pairs = [
        (key, value)
        for key, value in parse_qsl(parts.query, keep_blank_values=True)
        if key.lower() not in TRACKING_PARAMS
    ]
    query = urlencode(sorted(query_pairs))
    return urlunsplit((scheme, host, path, query, ""))


def normalize_title_company(title: str, company: str) -> str:
    blob = f"{title} {company}".lower()
    blob = re.sub(r"[^a-z0-9]+", " ", blob)
    return re.sub(r"\s+", " ", blob).strip()


def identity_hash(title: str, company: str) -> str:
    key = normalize_title_company(title, company)
    return hashlib.sha256(key.encode("utf-8")).hexdigest()[:16]


def similar(left: str, right: str) -> float:
    if not left or not right:
        return 0.0
    return SequenceMatcher(a=left, b=right).ratio()


class SeenStore:
    """JSON-backed set of already-seen job identities."""

    def __init__(self, path: Path) -> None:
        self.path = path
        self.ids: set[str] = set()
        self.urls: set[str] = set()
        self.identities: set[str] = set()
        self._load()

    def _load(self) -> None:
        if not self.path.is_file():
            return
        try:
            payload = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            log.warning("could not read seen file %s: %s", self.path, exc)
            return
        self.ids = set(payload.get("ids") or [])
        self.urls = set(payload.get("urls") or [])
        self.identities = set(payload.get("identities") or [])

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "ids": sorted(self.ids),
            "urls": sorted(self.urls),
            "identities": sorted(self.identities),
        }
        self.path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")

    def remember(self, job: Job) -> None:
        self.ids.add(job.id)
        url = normalize_url(job.url)
        if url:
            self.urls.add(url)
        ident = identity_hash(job.title, job.company)
        if ident:
            self.identities.add(ident)


def dedupe(
    jobs: list[Job],
    store: SeenStore | None = None,
    similarity: float = DEFAULT_SIMILARITY,
) -> list[Job]:
    """Drop exact URL clones, near-duplicate title+company pairs, and seen IDs."""

    kept: list[Job] = []
    seen_urls: set[str] = set(store.urls if store else ())
    seen_ids: set[str] = set(store.ids if store else ())
    seen_identities: set[str] = set(store.identities if store else ())
    kept_keys: list[str] = []

    for job in jobs:
        url = normalize_url(job.url)
        ident = identity_hash(job.title, job.company)
        key = normalize_title_company(job.title, job.company)

        if job.id in seen_ids:
            log.debug("skip seen id %s", job.id)
            continue
        if url and url in seen_urls:
            log.debug("skip duplicate url %s", url)
            continue
        if ident and ident in seen_identities:
            log.debug("skip known identity %s", ident)
            continue
        if key and any(similar(key, previous) >= similarity for previous in kept_keys):
            log.debug("skip similar title+company %s", key)
            continue

        kept.append(job)
        if url:
            seen_urls.add(url)
        seen_ids.add(job.id)
        if ident:
            seen_identities.add(ident)
        if key:
            kept_keys.append(key)

    return kept
