from __future__ import annotations

from decimal import Decimal, InvalidOperation
from datetime import datetime, timezone
from hashlib import sha256
import json
import re
from typing import Any
import unicodedata
from uuid import UUID


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
SCIENTIFIC_RESULT_KEYS = {
    "assay_code",
    "analyte_code",
    "method_code",
    "method_revision",
    "assay_specification_id",
    "specification_version",
    "raw_value_lexeme",
    "raw_value",
    "source_unit",
    "canonical_value",
    "canonical_unit",
    "unit_vocabulary",
    "unit_vocabulary_version",
    "unit_mapping_revision",
    "conversion_rule_version",
    "rounding_mode",
    "qualifier",
    "reference_interval",
    "detection_limits",
    "observed_at",
    "recorded_at",
    "quality_flag",
}


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
    if fixture["fixture_class"] != "synthetic" or fixture["fixture_version"] != "2.0.0":
        raise SyntheticBoundary("simulation fixture requires the synthetic 2.0.0 contract")
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
    _validate_scientific_result(fixture["result"])


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


def _validate_scientific_result(result: dict[str, Any]) -> None:
    if set(result) != SCIENTIFIC_RESULT_KEYS:
        raise SyntheticBoundary(
            "result requires the released assay quantity unit and provenance fields"
        )
    try:
        UUID(result["assay_specification_id"])
    except (TypeError, ValueError, AttributeError) as error:
        raise SyntheticBoundary("result assay specification requires a UUID") from error
    for field in ("method_revision", "specification_version"):
        if type(result[field]) is not int or result[field] < 1:
            raise SyntheticBoundary(f"result {field} requires a positive integer")
    for field in (
        "assay_code",
        "analyte_code",
        "method_code",
        "raw_value_lexeme",
        "source_unit",
        "unit_vocabulary_version",
        "unit_mapping_revision",
        "conversion_rule_version",
    ):
        if not isinstance(result[field], str) or not result[field].strip():
            raise SyntheticBoundary(f"result {field} requires bounded text")
    if result["canonical_unit"] != "{copies}/uL" or result["unit_vocabulary"] != "UCUM":
        raise SyntheticBoundary("result requires its versioned canonical UCUM unit")
    if result["rounding_mode"] not in {"half_even", "half_up", "toward_zero"}:
        raise SyntheticBoundary("result rounding mode requires a released value")
    if result["qualifier"] not in {None, "estimated", "less_than", "greater_than"}:
        raise SyntheticBoundary("result qualifier requires a released value")
    if result["quality_flag"] not in {"pass", "review", "quarantined"}:
        raise SyntheticBoundary("result quality flag requires a released value")
    _bounded_decimal(result["raw_value"], "result raw value")
    _bounded_decimal(result["canonical_value"], "result canonical value")
    intervals = (
        (result["reference_interval"], {"lower", "upper"}, "reference interval"),
        (
            result["detection_limits"],
            {"lower", "upper_quantitation"},
            "detection limits",
        ),
    )
    for value, fields, label in intervals:
        if not isinstance(value, dict) or set(value) != fields:
            raise SyntheticBoundary(f"result {label} requires its released bounds")
        for bound in value.values():
            _bounded_decimal(bound, f"result {label} bound")
    observed_at = _fixture_instant(result["observed_at"], "result observed_at")
    recorded_at = _fixture_instant(result["recorded_at"], "result recorded_at")
    if recorded_at < observed_at:
        raise SyntheticBoundary(
            "result recording time requires observation-time ordering"
        )


def _bounded_decimal(value: Any, label: str) -> Decimal:
    if not isinstance(value, str):
        raise SyntheticBoundary(f"{label} requires a decimal string")
    try:
        parsed = Decimal(value)
    except InvalidOperation as error:
        raise SyntheticBoundary(f"{label} requires a finite decimal") from error
    if not parsed.is_finite() or abs(parsed.as_tuple().exponent) > 12:
        raise SyntheticBoundary(
            f"{label} requires a finite value with at most 12 decimal places"
        )
    return parsed


def _fixture_instant(value: Any, label: str) -> datetime:
    if not isinstance(value, str):
        raise SyntheticBoundary(f"{label} requires a UTC instant")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as error:
        raise SyntheticBoundary(f"{label} requires an ISO-8601 instant") from error
    if parsed.tzinfo != timezone.utc:
        raise SyntheticBoundary(f"{label} requires UTC")
    return parsed
