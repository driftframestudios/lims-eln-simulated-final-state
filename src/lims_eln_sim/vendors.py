from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass, field
from typing import Any

from .domain import digest


class IdempotencyConflict(RuntimeError):
    """A stable request identity already binds to different content."""


class AmbiguousWrite(RuntimeError):
    """The caller receives uncertainty and reconciles by authoritative readback."""


@dataclass
class VendorWrite:
    request_id: str
    content_digest: str
    record: dict[str, Any]


@dataclass
class VendorEmulator:
    name: str
    version: str
    records: dict[str, dict[str, Any]] = field(default_factory=dict)
    writes: dict[str, VendorWrite] = field(default_factory=dict)
    event_queue: list[dict[str, Any]] = field(default_factory=list)

    def write(
        self,
        request_id: str,
        external_id: str,
        payload: dict[str, Any],
        *,
        outcome: str = "acknowledged",
    ) -> dict[str, Any]:
        content_digest = digest(payload)
        prior = self.writes.get(request_id)
        if prior and prior.content_digest != content_digest:
            raise IdempotencyConflict(f"{self.name} request identity binds to established content")
        if prior:
            return deepcopy(prior.record)

        record = {
            "vendor": self.name,
            "vendor_version": self.version,
            "external_id": external_id,
            "payload": deepcopy(payload),
            "content_digest": content_digest,
        }
        self.records[external_id] = record
        self.writes[request_id] = VendorWrite(request_id, content_digest, record)
        self.event_queue.append(
            {
                "event_id": f"{self.name.lower()}-{len(self.event_queue) + 1:04d}",
                "external_id": external_id,
                "signal": "record.changed",
            }
        )
        if outcome == "commit_with_uncertain_response":
            raise AmbiguousWrite(f"{self.name} committed; authoritative readback resolves the caller state")
        return deepcopy(record)

    def read(self, external_id: str) -> dict[str, Any]:
        return deepcopy(self.records[external_id])

    def reconcile(self, request_id: str) -> dict[str, Any]:
        return deepcopy(self.writes[request_id].record)


class SapioEmulator(VendorEmulator):
    def __init__(self) -> None:
        super().__init__(name="Sapio", version="simulated-tenant-2026.3")

    def write_graph(
        self,
        request_id: str,
        specimen: dict[str, Any],
        aliquots: list[dict[str, Any]],
        *,
        outcome: str = "acknowledged",
    ) -> dict[str, Any]:
        graph = {"specimen": specimen, "aliquots": aliquots}
        return self.write(request_id, specimen["specimen_id"], graph, outcome=outcome)


class BenchlingEmulator(VendorEmulator):
    def __init__(self) -> None:
        super().__init__(name="Benchling", version="simulated-v3-2026.3")

    def deliver_event(self, index: int = 0) -> dict[str, Any]:
        event = deepcopy(self.event_queue[index])
        event["interpretation"] = "signal_only_authoritative_read_required"
        return event


class LabKeyEmulator(VendorEmulator):
    def __init__(self) -> None:
        super().__init__(name="LabKey", version="simulated-4.3.0")

    def validate_rows(self, rows: list[dict[str, Any]]) -> dict[str, Any]:
        required = {"specimen_id", "status", "revision"}
        issues = [
            {"row": index, "missing": sorted(required - row.keys())}
            for index, row in enumerate(rows)
            if required - row.keys()
        ]
        return {"valid": len(issues) == 0, "issues": issues, "row_count": len(rows)}

