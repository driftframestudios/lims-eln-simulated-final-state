from __future__ import annotations

from dataclasses import dataclass, field
from hashlib import sha256
import hmac
import json
import re
from typing import Any
import unicodedata


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


PROTECTED_KEYS = {
    "accesskey",
    "accesstoken",
    "address",
    "apikey",
    "authorization",
    "clientsecret",
    "cookie",
    "dateofbirth",
    "dob",
    "email",
    "mrn",
    "name",
    "password",
    "passwd",
    "patientid",
    "phone",
    "privatekey",
    "secret",
    "session",
    "ssn",
    "subjectid",
    "token",
}


def redact_trace(payload: dict[str, Any], *, key: bytes) -> dict[str, Any]:
    if len(key) < 32:
        raise ValueError("trace pseudonymization requires at least 32 bytes of injected key material")
    return _redact(payload, key)


def _redact(value: Any, key: bytes) -> Any:
    if isinstance(value, dict):
        safe: dict[str, Any] = {}
        for field, item in value.items():
            normalized = re.sub(
                r"[^a-z0-9]",
                "",
                unicodedata.normalize("NFKC", str(field)).casefold(),
            )
            protected = normalized in PROTECTED_KEYS or any(
                normalized.endswith(part)
                for part in ("password", "secret", "token", "privatekey", "apikey")
            )
            safe[field] = (
                {
                    "classification": "protected",
                    "pseudonym": _keyed_pseudonym(item, key),
                }
                if protected
                else _redact(item, key)
            )
        return safe
    if isinstance(value, list):
        return [_redact(item, key) for item in value]
    return value


def _keyed_pseudonym(value: Any, key: bytes) -> str:
    canonical = json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        allow_nan=False,
    )
    return f"hmac-sha256:{hmac.new(key, canonical.encode(), sha256).hexdigest()}"


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
