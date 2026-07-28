from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .domain import digest


class AuthorizationBoundary(PermissionError):
    """The request receives an explicit boundary and a governed escalation path."""


@dataclass(frozen=True)
class Principal:
    principal_id: str
    tenant_id: str
    roles: tuple[str, ...]


def authorize(principal: Principal, tenant_id: str, required_role: str) -> dict[str, str]:
    if principal.tenant_id != tenant_id:
        raise AuthorizationBoundary("tenant boundary applied; submit through the governed transfer workflow")
    if required_role not in principal.roles:
        raise AuthorizationBoundary(f"role {required_role!r} required; request accountable role assignment")
    return {
        "decision": "allow",
        "principal_id": principal.principal_id,
        "tenant_id": tenant_id,
        "role": required_role,
    }


def redact_trace(payload: dict[str, Any]) -> dict[str, Any]:
    safe = {}
    classified = {"name", "email", "phone", "subject_id", "secret", "token"}
    for key, value in payload.items():
        safe[key] = {"classification": "protected", "digest": digest(value)} if key in classified else value
    return safe


@dataclass
class MetricBook:
    counters: dict[str, dict[str, int]] = field(default_factory=dict)

    def observe(self, metric: str, good: bool) -> None:
        counter = self.counters.setdefault(metric, {"good": 0, "valid": 0})
        counter["valid"] += 1
        counter["good"] += int(good)

    def summary(self) -> dict[str, Any]:
        return {
            name: {
                **counts,
                "ratio": counts["good"] / counts["valid"] if counts["valid"] else 1.0,
            }
            for name, counts in sorted(self.counters.items())
        }

