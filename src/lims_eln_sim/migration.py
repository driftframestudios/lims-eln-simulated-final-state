from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
import math
import re
from typing import Any
from uuid import UUID

from .domain import digest, parse_instant


CANONICAL_FIELDS = (
    "tenant_id",
    "external_tenant_id",
    "specimen_id",
    "external_specimen_id",
    "status",
    "revision",
    "result",
    "artifact_digest",
    "audit",
)
CORPUS_FIELDS = {
    "fixture_class",
    "fixture_version",
    "profile",
    "artifacts",
    "records",
}
SHA256_PATTERN = re.compile(r"^sha256:[a-f0-9]{64}$")
HEX_SHA256_PATTERN = re.compile(r"^[a-f0-9]{64}$")
CANONICAL_UTC_PATTERN = re.compile(
    r"^[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}\.[0-9]{3}Z$"
)
RESULT_FIELDS = {
    "assay_specification_id",
    "specification_version",
    "assay_code",
    "analyte_code",
    "method_code",
    "method_revision",
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
    "content_digest",
}


@dataclass(frozen=True)
class MigrationReport:
    source_count: int
    target_count: int
    source_digest: str
    target_digest: str
    semantic_parity: bool
    rollback_ready: bool
    mismatch_paths: tuple[str, ...]


class MigrationHarness:
    def migrate(
        self,
        records: list[dict[str, Any]],
        *,
        failure_twin: str | None = None,
    ) -> tuple[list[dict[str, Any]], MigrationReport]:
        identities = [
            (record.get("tenant_id"), record.get("specimen_id"))
            for record in records
        ]
        if len(identities) != len(set(identities)):
            raise ValueError(
                "migration source requires one record per tenant and specimen identity"
            )
        source_projection = [self._source_projection(record) for record in records]
        target = [self._target_projection(record) for record in records]
        if failure_twin == "changed-scientific-result" and target:
            target[0]["result"] = {
                **(target[0].get("result") or {}),
                "quality_flag": "failure-twin-drift",
            }
        elif failure_twin == "missing-audit-event" and target and target[0]["audit"]:
            target[0]["audit"] = target[0]["audit"][:-1]
        elif failure_twin is not None:
            raise ValueError("failure_twin requires a released migration scenario")

        mismatches = tuple(_difference_paths(source_projection, target))
        rollback_ready = bool(records) and all(
            _record_rollback_ready(record) for record in source_projection
        )
        report = MigrationReport(
            source_count=len(source_projection),
            target_count=len(target),
            source_digest=digest(source_projection),
            target_digest=digest(target),
            semantic_parity=not mismatches,
            rollback_ready=rollback_ready,
            mismatch_paths=mismatches,
        )
        return target, report

    def restore(
        self,
        snapshot: list[dict[str, Any]],
        *,
        expected_digest: str,
        clean_environment: bool,
        recovery_objective_seconds: float,
        observed_recovery_seconds: float,
        failure_twin: str | None = None,
    ) -> dict[str, Any]:
        durations = (recovery_objective_seconds, observed_recovery_seconds)
        if any(
            not isinstance(value, (int, float))
            or isinstance(value, bool)
            or value < 0
            or not math.isfinite(value)
            for value in durations
        ):
            raise ValueError("restore durations require finite, nonnegative values")
        if not isinstance(clean_environment, bool):
            raise ValueError("clean_environment requires an observed boolean state")
        restored = deepcopy(snapshot)
        if failure_twin == "missing-restored-record" and restored:
            restored.pop()
        elif failure_twin == "changed-restored-result" and restored:
            restored[0]["result"] = {
                **(restored[0].get("result") or {}),
                "quality_flag": "failure-twin-restore-drift",
            }
        elif failure_twin is not None:
            raise ValueError("failure_twin requires a released restore scenario")

        readback_digest = digest(restored)
        readback_parity = readback_digest == expected_digest
        objective_met = observed_recovery_seconds <= recovery_objective_seconds
        return {
            "clean_environment": clean_environment,
            "record_count": len(restored),
            "expected_artifact_and_record_digest": expected_digest,
            "artifact_and_record_digest": readback_digest,
            "readback_parity": readback_parity,
            "field_manifest": _field_manifest(restored),
            "recovery_objective_seconds": recovery_objective_seconds,
            "observed_recovery_seconds": observed_recovery_seconds,
            "recovery_point_seconds": 0,
            "recovery_objective_met": objective_met,
            "qualification_ready": clean_environment and readback_parity and objective_met,
        }

    def data_exit(self, snapshot: list[dict[str, Any]]) -> dict[str, Any]:
        required = set(CANONICAL_FIELDS)
        field_manifest = _field_manifest(snapshot)
        reconstructable = bool(snapshot) and all(required <= set(record) for record in snapshot)
        return {
            "neutral_format": "canonical-json-v1",
            "record_count": len(snapshot),
            "field_manifest": field_manifest,
            "reconstructable": reconstructable,
            "digest": digest(snapshot),
        }

    @staticmethod
    def _source_projection(record: dict[str, Any]) -> dict[str, Any]:
        return {field: deepcopy(record.get(field)) for field in CANONICAL_FIELDS}

    @staticmethod
    def _target_projection(record: dict[str, Any]) -> dict[str, Any]:
        return {field: deepcopy(record.get(field)) for field in CANONICAL_FIELDS}


def _field_manifest(records: list[dict[str, Any]]) -> list[str]:
    return sorted({field for record in records for field in record})


def validate_representative_corpus(corpus: dict[str, Any]) -> list[dict[str, Any]]:
    """Return a closed, representative synthetic migration record set."""

    if set(corpus) != CORPUS_FIELDS:
        raise ValueError(
            "representative migration corpus requires released fixture, profile, "
            "artifact, and record fields"
        )
    if (
        corpus.get("fixture_class") != "representative_synthetic"
        or corpus.get("fixture_version") != "2.0.0"
    ):
        raise ValueError(
            "representative migration corpus requires the released synthetic fixture contract"
        )
    profile = corpus.get("profile")
    if not isinstance(profile, dict) or set(profile) != {
        "records",
        "result_records",
        "tenant_count",
        "lineage_depth",
        "artifact_sizes_bytes",
        "assay_specification_versions",
        "unit_mapping_revisions",
        "qualifier_classes",
        "exception_classes",
    }:
        raise ValueError("representative migration profile requires released dimensions")
    if type(profile["records"]) is not int or profile["records"] < 1:
        raise ValueError(
            "representative migration profile record count requires a positive integer"
        )
    for field in ("result_records", "tenant_count"):
        if type(profile[field]) is not int or profile[field] < 1:
            raise ValueError(
                f"representative migration profile {field} requires a positive integer"
            )
    for field in ("lineage_depth", "artifact_sizes_bytes"):
        values = profile[field]
        if (
            not isinstance(values, list)
            or not values
            or any(type(item) is not int or item < 1 for item in values)
        ):
            raise ValueError(
                f"representative migration profile {field} requires positive integers"
            )
    records = corpus.get("records")
    artifacts = corpus.get("artifacts")
    if not isinstance(records, list) or not isinstance(artifacts, list):
        raise ValueError("representative migration corpus requires record and artifact arrays")
    if profile["records"] != len(records) or len(records) < 4:
        raise ValueError("representative migration corpus requires its declared record count")
    identities = set()
    external_identities = set()
    tenant_ids = set()
    artifact_digests = set()
    artifact_sizes = []
    for artifact in artifacts:
        if not isinstance(artifact, dict) or set(artifact) != {
            "artifact_id",
            "size_bytes",
            "digest",
        }:
            raise ValueError("representative artifact requires identity, size, and digest")
        if (
            type(artifact["size_bytes"]) is not int
            or artifact["size_bytes"] <= 0
        ):
            raise ValueError("representative artifact size requires a positive integer")
        if (
            not isinstance(artifact["artifact_id"], str)
            or not artifact["artifact_id"].startswith("ART-SYN-")
            or not isinstance(artifact["digest"], str)
            or SHA256_PATTERN.fullmatch(artifact["digest"]) is None
        ):
            raise ValueError(
                "representative artifact requires generated identity and canonical digest"
            )
        artifact_sizes.append(artifact["size_bytes"])
        artifact_digests.add(artifact["digest"])
    lineage_depth = []
    for record in records:
        if not isinstance(record, dict) or set(record) != set(CANONICAL_FIELDS):
            raise ValueError(
                "representative migration record requires the canonical field set"
            )
        identity = (record["tenant_id"], record["specimen_id"])
        if identity in identities:
            raise ValueError(
                "representative migration corpus requires unique specimen identities"
            )
        identities.add(identity)
        try:
            UUID(record["tenant_id"])
            UUID(record["specimen_id"])
        except (TypeError, ValueError, AttributeError) as error:
            raise ValueError(
                "representative migration corpus requires internal UUID identities"
            ) from error
        if (
            not isinstance(record["external_tenant_id"], str)
            or not record["external_tenant_id"].startswith("TENANT-SYN-")
            or not isinstance(record["external_specimen_id"], str)
            or not record["external_specimen_id"].startswith("SPM-SYN-")
        ):
            raise ValueError(
                "representative migration corpus requires generated external identities"
            )
        external_identity = (
            record["tenant_id"],
            record["external_specimen_id"],
        )
        if external_identity in external_identities:
            raise ValueError(
                "representative migration corpus requires tenant-scoped external identity"
            )
        external_identities.add(external_identity)
        tenant_ids.add(record["tenant_id"])
        if type(record["revision"]) is not int or record["revision"] < 1:
            raise ValueError(
                "representative migration revision requires a positive integer"
            )
        if not isinstance(record["artifact_digest"], str) or SHA256_PATTERN.fullmatch(
            record["artifact_digest"]
        ) is None:
            raise ValueError(
                "representative record artifact requires a canonical digest"
            )
        if record["artifact_digest"] not in artifact_digests:
            raise ValueError(
                "representative record artifact requires a declared corpus artifact"
            )
        _validate_scientific_result(record["result"])
        if not isinstance(record["audit"], list) or not record["audit"]:
            raise ValueError(
                "representative migration record requires reconstructable audit lineage"
            )
        expected_sequences = list(range(1, len(record["audit"]) + 1))
        observed_sequences = []
        for event in record["audit"]:
            if not isinstance(event, dict) or set(event) != {
                "sequence",
                "event",
                "occurred_at",
                "recorded_at",
            }:
                raise ValueError(
                    "representative audit event requires sequence identity occurrence and recording fields"
                )
            if type(event["sequence"]) is not int or event["sequence"] < 1:
                raise ValueError(
                    "representative audit sequence requires a positive integer"
                )
            if not isinstance(event["event"], str) or not event["event"].strip():
                raise ValueError(
                    "representative audit event requires a released event identity"
                )
            occurred_at = _canonical_instant(
                event["occurred_at"], "representative audit occurrence"
            )
            recorded_at = _canonical_instant(
                event["recorded_at"], "representative audit recording"
            )
            if recorded_at < occurred_at:
                raise ValueError(
                    "representative audit recording time requires occurrence-time ordering"
                )
            observed_sequences.append(event["sequence"])
        if observed_sequences != expected_sequences:
            raise ValueError(
                "representative audit lineage requires contiguous ordered sequences"
            )
        if record["revision"] != len(record["audit"]):
            raise ValueError(
                "representative revision requires the complete audit lineage depth"
            )
        lineage_depth.append(len(record["audit"]))
    if len(tenant_ids) != profile["tenant_count"]:
        raise ValueError(
            "representative migration corpus requires its declared tenant count"
        )
    result_records = [record["result"] for record in records if record["result"] is not None]
    if len(result_records) != profile["result_records"]:
        raise ValueError(
            "representative migration corpus requires its declared result count"
        )
    if sorted({item["specification_version"] for item in result_records}) != sorted(
        profile["assay_specification_versions"]
    ):
        raise ValueError(
            "representative migration corpus requires its declared assay specification versions"
        )
    if sorted({item["unit_mapping_revision"] for item in result_records}) != sorted(
        profile["unit_mapping_revisions"]
    ):
        raise ValueError(
            "representative migration corpus requires its declared unit mapping revisions"
        )
    qualifier_classes = {
        "unqualified" if item["qualifier"] is None else item["qualifier"]
        for item in result_records
    }
    if qualifier_classes != set(profile["qualifier_classes"]):
        raise ValueError(
            "representative migration corpus requires its declared qualifier classes"
        )
    if sorted(artifact_sizes) != sorted(profile["artifact_sizes_bytes"]):
        raise ValueError(
            "representative artifact sizes differ from the declared profile"
        )
    if sorted(lineage_depth) != sorted(profile["lineage_depth"]):
        raise ValueError(
            "representative lineage depths differ from the declared profile"
        )
    required_exceptions = {
        "duplicate-replay",
        "changed-content",
        "stale-revision",
        "missing-artifact",
    }
    if set(profile["exception_classes"]) != required_exceptions:
        raise ValueError(
            "representative migration profile requires every released exception class"
        )
    return deepcopy(records)


def _record_rollback_ready(record: dict[str, Any]) -> bool:
    revision = record.get("revision")
    audit = record.get("audit")
    if (
        type(revision) is not int
        or revision < 1
        or not isinstance(record.get("artifact_digest"), str)
        or SHA256_PATTERN.fullmatch(record["artifact_digest"]) is None
        or not isinstance(audit, list)
        or len(audit) != revision
    ):
        return False
    return all(
        isinstance(event, dict)
        and set(event)
        == {"sequence", "event", "occurred_at", "recorded_at"}
        and type(event["sequence"]) is int
        and event["sequence"] == sequence
        and isinstance(event["event"], str)
        and bool(event["event"].strip())
        and _is_canonical_ordered_instant_pair(event)
        for sequence, event in enumerate(audit, start=1)
    )


def _validate_scientific_result(value: Any) -> None:
    if value is None:
        return
    if not isinstance(value, dict) or set(value) != RESULT_FIELDS:
        raise ValueError(
            "representative result requires the released scientific quantity field set"
        )
    try:
        UUID(value["assay_specification_id"])
    except (TypeError, ValueError, AttributeError) as error:
        raise ValueError(
            "representative result requires an assay specification UUID"
        ) from error
    for field in ("specification_version", "method_revision"):
        if type(value[field]) is not int or value[field] < 1:
            raise ValueError(
                f"representative result {field} requires a positive integer"
            )
    for field in (
        "assay_code",
        "analyte_code",
        "method_code",
        "raw_value_lexeme",
        "source_unit",
        "unit_vocabulary_version",
        "unit_mapping_revision",
        "conversion_rule_version",
        "rounding_mode",
    ):
        if not isinstance(value[field], str) or not value[field].strip():
            raise ValueError(f"representative result {field} requires bounded text")
    if value["unit_vocabulary"] != "UCUM" or value["canonical_unit"] != "{copies}/uL":
        raise ValueError(
            "representative result requires its versioned canonical UCUM unit"
        )
    if value["qualifier"] not in {None, "estimated", "less_than", "greater_than"}:
        raise ValueError("representative result qualifier requires a released value")
    for field in ("raw_value", "canonical_value"):
        _exact_decimal(value[field], f"representative result {field}")
    for field in ("reference_interval", "detection_limits"):
        interval = value[field]
        expected = (
            {"lower", "upper"}
            if field == "reference_interval"
            else {"lower", "upper_quantitation"}
        )
        if not isinstance(interval, dict) or set(interval) != expected:
            raise ValueError(
                f"representative result {field} requires its released bounds"
            )
        for bound in interval.values():
            _exact_decimal(bound, f"representative result {field} bound")
    observed_at = _canonical_instant(
        value["observed_at"], "representative result observed_at"
    )
    recorded_at = _canonical_instant(
        value["recorded_at"], "representative result recorded_at"
    )
    if recorded_at < observed_at:
        raise ValueError(
            "representative result recording time requires observation-time ordering"
        )
    content_digest = value["content_digest"]
    if not isinstance(content_digest, dict) or set(content_digest) != {
        "algorithm",
        "encoding",
        "value",
        "canonicalization_profile",
        "content_scope",
    }:
        raise ValueError(
            "representative result digest requires algorithm encoding canonicalization and scope"
        )
    if (
        content_digest["algorithm"] != "sha256"
        or content_digest["encoding"] != "hex"
        or not isinstance(content_digest["value"], str)
        or HEX_SHA256_PATTERN.fullmatch(content_digest["value"]) is None
        or content_digest["canonicalization_profile"]
        != "RFC-8785-compatible-v1"
        or not isinstance(content_digest["content_scope"], str)
        or len(content_digest["content_scope"].strip()) < 10
    ):
        raise ValueError(
            "representative result digest requires a 32-byte SHA-256 semantic envelope"
        )


def _exact_decimal(value: Any, label: str) -> Decimal:
    if not isinstance(value, str):
        raise ValueError(f"{label} requires a canonical decimal string")
    try:
        decimal_value = Decimal(value)
    except InvalidOperation as error:
        raise ValueError(f"{label} requires a finite decimal") from error
    if not decimal_value.is_finite() or abs(decimal_value.as_tuple().exponent) > 12:
        raise ValueError(f"{label} requires a finite value with at most 12 decimal places")
    return decimal_value


def _canonical_instant(value: Any, label: str):
    if not isinstance(value, str) or CANONICAL_UTC_PATTERN.fullmatch(value) is None:
        raise ValueError(f"{label} requires millisecond canonical UTC")
    return parse_instant(value, label=label)


def _is_canonical_ordered_instant_pair(event: dict[str, Any]) -> bool:
    try:
        occurred_at = _canonical_instant(event["occurred_at"], "audit occurrence")
        recorded_at = _canonical_instant(event["recorded_at"], "audit recording")
    except ValueError:
        return False
    return recorded_at >= occurred_at


def _difference_paths(left: Any, right: Any, path: str = "$") -> list[str]:
    if type(left) is not type(right):
        return [path]
    if isinstance(left, dict):
        differences: list[str] = []
        for key in sorted(set(left) | set(right)):
            if key not in left or key not in right:
                differences.append(f"{path}.{key}")
            else:
                differences.extend(_difference_paths(left[key], right[key], f"{path}.{key}"))
        return differences
    if isinstance(left, list):
        differences = []
        if len(left) != len(right):
            differences.append(f"{path}.length")
        for index, (left_item, right_item) in enumerate(zip(left, right)):
            differences.extend(
                _difference_paths(left_item, right_item, f"{path}.{index}")
            )
        return differences
    return [] if left == right else [path]
