from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass
class Job:
    """Normalized job posting shared by every source adapter."""

    id: str
    title: str
    company: str
    url: str
    location: str = ""
    tags: list[str] = field(default_factory=list)
    source: str = ""
    description: str = ""
    status: str = "unverified"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Job:
        tags = data.get("tags") or []
        if isinstance(tags, str):
            tags = [part.strip() for part in tags.split(",") if part.strip()]
        return cls(
            id=str(data.get("id") or ""),
            title=str(data.get("title") or ""),
            company=str(data.get("company") or ""),
            url=str(data.get("url") or ""),
            location=str(data.get("location") or ""),
            tags=list(tags),
            source=str(data.get("source") or ""),
            description=str(data.get("description") or ""),
            status=str(data.get("status") or "unverified"),
        )
