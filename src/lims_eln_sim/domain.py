from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass, field
from datetime import datetime, timezone
from hashlib import sha256
import json
from typing import Any


ALLOWED_TRANSITIONS = {
    "received": {"accessioned"},
    "accessioned": {"in_custody"},
    "in_custody": {"instrument_complete"},
    "instrument_complete": {"reviewed"},
    "reviewed": {"released"},
    "released": {"corrected"},
    "corrected": {"released"},
}


class DomainRuleError(ValueError):
    """Raised when a requested transition falls outside the released rules."""


@dataclass(frozen=True)
class AuditEvent:
    event_id: str
    action: str
    actor: str
    occurred_at: datetime
    revision: int
    detail_digest: str

    def as_dict(self) -> dict[str, Any]:
        return {
            "event_id": self.event_id,
            "action": self.action,
            "actor": self.actor,
            "occurred_at": canonical_utc(self.occurred_at),
            "revision": self.revision,
            "detail_digest": self.detail_digest,
        }


@dataclass
class Specimen:
    specimen_id: str
    tenant_id: str
    source_alias: str
    status: str = "received"
    revision: int = 0
    custody_location: str | None = None
    result: dict[str, Any] | None = None
    artifact_digest: str | None = None
    audit: list[AuditEvent] = field(default_factory=list)

    def transition(
        self,
        target: str,
        actor: str,
        detail: dict[str, Any],
        occurred_at: str | datetime,
    ) -> None:
        if target not in ALLOWED_TRANSITIONS.get(self.status, set()):
            raise DomainRuleError(f"transition {self.status!r} -> {target!r} requires a released rule")
        self.status = target
        self.revision += 1
        self.audit.append(
            AuditEvent(
                event_id=f"evt-{self.specimen_id}-{self.revision:03d}",
                action=target,
                actor=actor,
                occurred_at=parse_instant(occurred_at, label="audit occurred_at"),
                revision=self.revision,
                detail_digest=digest(detail),
            )
        )

    def view(self) -> dict[str, Any]:
        return {
            "specimen_id": self.specimen_id,
            "tenant_id": self.tenant_id,
            "source_alias": self.source_alias,
            "status": self.status,
            "revision": self.revision,
            "custody_location": self.custody_location,
            "result": deepcopy(self.result),
            "artifact_digest": self.artifact_digest,
            "audit": [event.as_dict() for event in self.audit],
        }


def utc_now() -> str:
    return canonical_utc(datetime.now(tz=timezone.utc))


def parse_instant(value: str | datetime, *, label: str = "instant") -> datetime:
    """Return one timezone-aware instant normalized to UTC."""

    if isinstance(value, datetime):
        parsed = value
    elif isinstance(value, str):
        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError as error:
            raise ValueError(f"{label} requires an ISO 8601 instant") from error
    else:
        raise ValueError(f"{label} requires a datetime or ISO 8601 instant")
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError(f"{label} requires an explicit timezone")
    return parsed.astimezone(timezone.utc)


def canonical_utc(value: datetime) -> str:
    """Serialize an aware datetime as canonical RFC 3339 UTC text."""

    instant = parse_instant(value)
    return instant.isoformat(timespec="milliseconds").replace("+00:00", "Z")


def canonical_json(value: Any) -> str:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        allow_nan=False,
    )


def digest(value: Any) -> str:
    return f"sha256:{sha256(canonical_json(value).encode()).hexdigest()}"
