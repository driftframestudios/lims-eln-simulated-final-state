from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
import math
from typing import Any

from .domain import digest


CANONICAL_FIELDS = (
    "specimen_id",
    "tenant_id",
    "status",
    "revision",
    "result",
    "artifact_digest",
    "audit",
)


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
            isinstance(record.get("revision"), int)
            and isinstance(record.get("artifact_digest"), str)
            and bool(record.get("audit"))
            for record in source_projection
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
        return {
            "specimen_id": record["specimen_id"],
            "tenant_id": record["tenant_id"],
            "status": record["status"],
            "revision": record["revision"],
            "result": deepcopy(record.get("result")),
            "artifact_digest": record.get("artifact_digest"),
            "audit": deepcopy(record.get("audit", [])),
        }

    @staticmethod
    def _target_projection(record: dict[str, Any]) -> dict[str, Any]:
        return {field: deepcopy(record.get(field)) for field in CANONICAL_FIELDS}


def _field_manifest(records: list[dict[str, Any]]) -> list[str]:
    return sorted({field for record in records for field in record})


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
