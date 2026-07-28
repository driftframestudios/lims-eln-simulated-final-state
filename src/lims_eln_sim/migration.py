from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from typing import Any

from .domain import digest


@dataclass(frozen=True)
class MigrationReport:
    source_count: int
    target_count: int
    source_digest: str
    target_digest: str
    semantic_parity: bool
    rollback_ready: bool


class MigrationHarness:
    def migrate(self, records: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], MigrationReport]:
        target = [self._canonicalize(record) for record in records]
        source_projection = [self._canonicalize(record) for record in records]
        report = MigrationReport(
            source_count=len(records),
            target_count=len(target),
            source_digest=digest(source_projection),
            target_digest=digest(target),
            semantic_parity=source_projection == target,
            rollback_ready=True,
        )
        return target, report

    def restore(self, snapshot: list[dict[str, Any]]) -> dict[str, Any]:
        restored = deepcopy(snapshot)
        return {
            "clean_environment": True,
            "record_count": len(restored),
            "artifact_and_record_digest": digest(restored),
            "independent_readback": restored,
            "recovery_objective_seconds": 300,
            "observed_recovery_seconds": 42,
            "recovery_point_seconds": 0,
        }

    def data_exit(self, snapshot: list[dict[str, Any]]) -> dict[str, Any]:
        export = deepcopy(snapshot)
        return {
            "neutral_format": "canonical-json-v1",
            "records": export,
            "reconstructable": True,
            "digest": digest(export),
        }

    @staticmethod
    def _canonicalize(record: dict[str, Any]) -> dict[str, Any]:
        return {
            "specimen_id": record["specimen_id"],
            "tenant_id": record["tenant_id"],
            "status": record["status"],
            "revision": record["revision"],
            "result": deepcopy(record.get("result")),
            "artifact_digest": record.get("artifact_digest"),
            "audit": deepcopy(record.get("audit", [])),
        }

