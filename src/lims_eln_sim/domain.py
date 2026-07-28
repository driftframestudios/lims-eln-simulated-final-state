from __future__ import annotations

from dataclasses import asdict, dataclass, field
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
    occurred_at: str
    revision: int
    detail_digest: str


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
        occurred_at: str,
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
                occurred_at=occurred_at,
                revision=self.revision,
                detail_digest=digest(detail),
            )
        )

    def view(self) -> dict[str, Any]:
        return asdict(self)


def utc_now() -> str:
    return datetime.now(tz=timezone.utc).isoformat()


def canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def digest(value: Any) -> str:
    return f"sha256:{sha256(canonical_json(value).encode()).hexdigest()}"

