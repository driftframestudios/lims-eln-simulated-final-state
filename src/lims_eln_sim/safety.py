from __future__ import annotations

from datetime import datetime, timezone
from hashlib import sha256
import json
import re
from typing import Any
import unicodedata


FIXTURE_KEYS = {
    "artifact",
    "clock",
    "fixture_class",
    "fixture_version",
    "interpretation",
    "observed_recovery_seconds",
    "recovery_objective_seconds",
    "redaction_key_id",
    "result",
    "run_id",
    "runtime_configuration",
    "source_alias",
    "specimen_id",
    "tenant_id",
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
SECRET_PATTERNS = (
    re.compile(r"\b(?:AKIA|ASIA)[A-Z0-9]{16}\b"),
    re.compile(r"\bgithub_pat_[A-Za-z0-9_]{20,255}\b"),
    re.compile(r"\bgh[pousr]_[A-Za-z0-9_]{20,255}\b"),
    re.compile(r"\bsk-[A-Za-z0-9_-]{20,}\b"),
    re.compile(r"\bxox[baprs]-[A-Za-z0-9-]{10,}\b"),
    re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH |DSA |PGP )?PRIVATE KEY-----"),
    re.compile(r"\bBearer\s+[A-Za-z0-9._~+/=-]{12,}\b", re.IGNORECASE),
)


class SyntheticBoundary(ValueError):
    """A fixture receives a generated-data replacement path before simulation."""


def validate_synthetic_fixture(fixture: Any) -> None:
    if not isinstance(fixture, dict):
        raise SyntheticBoundary("simulation fixture requires a JSON object")
    missing = sorted(FIXTURE_KEYS - fixture.keys())
    extra = sorted(fixture.keys() - FIXTURE_KEYS)
    if missing:
        raise SyntheticBoundary(f"simulation fixture requires fields: {', '.join(missing)}")
    if extra:
        raise SyntheticBoundary(
            f"simulation fixture fields require a released definition: {', '.join(extra)}"
        )
    if fixture["fixture_class"] != "synthetic" or fixture["fixture_version"] != "1.0.0":
        raise SyntheticBoundary("simulation fixture requires the synthetic 1.0.0 contract")
    prefixes = {
        "tenant_id": "TENANT-SYN-",
        "specimen_id": "SPM-SYN-",
        "source_alias": "ACCESSION-SYN-",
        "run_id": "RUN-SYN-",
        "redaction_key_id": "synthetic-key-",
    }
    for field, prefix in prefixes.items():
        value = fixture[field]
        if not isinstance(value, str) or not value.startswith(prefix):
            raise SyntheticBoundary(f"{field} requires the generated {prefix} namespace")
    try:
        observed = datetime.fromisoformat(str(fixture["clock"]).replace("Z", "+00:00"))
    except ValueError as error:
        raise SyntheticBoundary("clock requires an ISO-8601 timestamp") from error
    if observed.tzinfo != timezone.utc:
        raise SyntheticBoundary("clock requires the UTC simulation timeline")
    for field in ("observed_recovery_seconds", "recovery_objective_seconds"):
        value = fixture[field]
        if not isinstance(value, (int, float)) or isinstance(value, bool) or value < 0:
            raise SyntheticBoundary(f"{field} requires a nonnegative simulated duration")
    if fixture["observed_recovery_seconds"] > fixture["recovery_objective_seconds"] * 10:
        raise SyntheticBoundary(
            "observed recovery duration requires the bounded failure-simulation window"
        )
    artifact = fixture["artifact"]
    if not isinstance(artifact, dict) or set(artifact) != {"kind", "content"}:
        raise SyntheticBoundary("artifact requires the released synthetic kind and content fields")
    if not str(artifact["kind"]).startswith("synthetic-") or not str(artifact["content"]).startswith(
        "SYNTHETIC-"
    ):
        raise SyntheticBoundary("artifact requires generated synthetic markers")
    if not isinstance(fixture["result"], dict) or not isinstance(
        fixture["runtime_configuration"], dict
    ):
        raise SyntheticBoundary("result and runtime_configuration require JSON objects")
    _validate_safe_content(fixture)


def synthetic_redaction_key(key_id: str) -> bytes:
    if not key_id.startswith("synthetic-key-"):
        raise SyntheticBoundary("redaction key identity requires the synthetic-key namespace")
    return sha256(f"lims-eln-simulation|{key_id}".encode()).digest()


def _normalized_key(value: str) -> str:
    return re.sub(r"[^a-z0-9]", "", unicodedata.normalize("NFKC", value).casefold())


def _validate_safe_content(value: Any, path: str = "$") -> None:
    if isinstance(value, dict):
        for key, item in value.items():
            normalized = _normalized_key(str(key))
            if normalized in PROTECTED_KEYS or any(
                normalized.endswith(part)
                for part in ("password", "secret", "token", "privatekey", "apikey")
            ):
                raise SyntheticBoundary(
                    f"{path}.{key} represents protected content; use a generated reference identity"
                )
            _validate_safe_content(item, f"{path}.{key}")
        return
    if isinstance(value, list):
        for index, item in enumerate(value):
            _validate_safe_content(item, f"{path}[{index}]")
        return
    if isinstance(value, str) and any(pattern.search(value) for pattern in SECRET_PATTERNS):
        raise SyntheticBoundary(
            f"{path} resembles credential material; use a generated reference identity"
        )
    try:
        json.dumps(value, allow_nan=False)
    except (TypeError, ValueError) as error:
        raise SyntheticBoundary(f"{path} requires a finite JSON value") from error
