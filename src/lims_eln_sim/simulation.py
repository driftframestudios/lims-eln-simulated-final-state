from __future__ import annotations

from dataclasses import asdict
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
from typing import Any

from .assurance import MetricBook, redact_trace
from .configuration import (
    AwsRuntimeReference,
    SyntheticAwsProvider,
    resolve_runtime_configuration,
)
from .database_reference import inspect_database_reference
from .domain import Specimen, digest
from .migration import MigrationHarness, validate_representative_corpus
from .safety import validate_synthetic_fixture
from .vendors import (
    AmbiguousWrite,
    BenchlingEmulator,
    LabKeyEmulator,
    SapioEmulator,
)


REFERENCE_VERSION = "vendor-evaluation-1.0"


def run(
    fixture: dict[str, Any],
    *,
    intended_use_profile: dict[str, Any],
    migration_corpus: dict[str, Any],
    database_reference: dict[str, Any],
    redaction_key: bytes,
) -> dict[str, Any]:
    """Evaluate vendor behavior and portability with synthetic records.

    The result is comparative engineering evidence with runtime effect set to
    none. Established systems retain production and organizational decisions.
    """

    validate_synthetic_fixture(fixture)
    _validate_intended_use_profile(intended_use_profile)
    clock = fixture["clock"]
    specimen = Specimen(
        specimen_id=fixture["specimen_id"],
        tenant_id=fixture["tenant_id"],
        source_alias=fixture["source_alias"],
    )
    specimen.result = fixture["result"]
    specimen.artifact_digest = digest(fixture["artifact"])
    transitions = (
        ("accessioned", "accessioner", {"alias": specimen.source_alias}),
        ("in_custody", "courier", {"location": "receiving-freezer-2"}),
        ("instrument_complete", "instrument-gateway", {"run_id": fixture["run_id"]}),
        ("reviewed", "scientist", {"interpretation": fixture["interpretation"]}),
        ("released", "pathologist", {"release_reason": "review-complete"}),
    )
    for offset, (status, actor, detail) in enumerate(transitions):
        specimen.transition(status, actor, detail, _event_time(clock, offset))

    sapio = SapioEmulator()
    try:
        sapio.write_graph(
            "req-sapio-0001",
            specimen.view(),
            [{"aliquot_id": "ALQ-SYN-001-A", "volume_ul": 250}],
            outcome="commit_with_uncertain_response",
        )
    except AmbiguousWrite:
        sapio_record = sapio.reconcile("req-sapio-0001")

    benchling = BenchlingEmulator()
    benchling_record = benchling.write(
        "req-benchling-0001", specimen.specimen_id, specimen.view()
    )
    benchling_event = benchling.deliver_event()
    benchling_readback = benchling.read(benchling_event["external_id"])

    labkey = LabKeyEmulator()
    rows = [
        {
            "specimen_id": specimen.specimen_id,
            "status": specimen.status,
            "revision": specimen.revision,
        }
    ]
    labkey_validation = labkey.validate_rows(rows)
    labkey_record = labkey.write(
        "req-labkey-0001", specimen.specimen_id, specimen.view()
    )

    representative_records = validate_representative_corpus(migration_corpus)
    migration = MigrationHarness()
    migrated, migration_report = migration.migrate(representative_records)
    _, migration_failure_report = migration.migrate(
        representative_records,
        failure_twin="changed-scientific-result",
    )
    restore_report = migration.restore(
        migrated,
        expected_digest=migration_report.target_digest,
        clean_environment=True,
        recovery_objective_seconds=fixture["recovery_objective_seconds"],
        observed_recovery_seconds=fixture["observed_recovery_seconds"],
    )
    restore_failure_report = migration.restore(
        migrated,
        expected_digest=migration_report.target_digest,
        clean_environment=True,
        recovery_objective_seconds=fixture["recovery_objective_seconds"],
        observed_recovery_seconds=fixture["observed_recovery_seconds"],
        failure_twin="missing-restored-record",
    )
    runtime_configuration = resolve_runtime_configuration(
        AwsRuntimeReference.from_dict(fixture["runtime_configuration"]),
        SyntheticAwsProvider(),
    )

    metrics = MetricBook()
    for record in (sapio_record, benchling_record, benchling_readback, labkey_record):
        metrics.observe(
            "vendor_projection_readback",
            record["external_id"] == specimen.specimen_id,
        )
    metrics.observe("migration_semantic_parity", migration_report.semantic_parity)
    metrics.observe(
        "restore_within_recovery_objective",
        restore_report["observed_recovery_seconds"]
        <= restore_report["recovery_objective_seconds"],
    )

    result = {
        "specimen": specimen.view(),
        "vendors": {
            "sapio": _vendor_manifest(sapio_record),
            "benchling": {
                "event": benchling_event,
                "authoritative_readback": _vendor_manifest(benchling_readback),
            },
            "labkey": {
                "validation": labkey_validation,
                "record": _vendor_manifest(labkey_record),
            },
        },
        "event_delivery": {
            "pattern": "thin_transactional_outbox",
            "envelope": benchling_event,
            "outcome": "readback_converged",
            "scope": "advisory comparison of an emitted vendor event and authoritative readback",
        },
        "migration": asdict(migration_report),
        "migration_corpus": {
            "record_count": len(representative_records),
            "artifact_count": len(migration_corpus["artifacts"]),
            "exception_classes": list(
                migration_corpus["profile"]["exception_classes"]
            ),
        },
        "database_reference": inspect_database_reference(database_reference),
        "restore": restore_report,
        "data_exit": migration.data_exit(migrated),
        "failure_twins": {
            "migration": asdict(migration_failure_report),
            "restore": restore_failure_report,
        },
        "runtime_configuration": runtime_configuration.reference,
        "trace_redaction_example": redact_trace(
            {
                "request_id": "req-sapio-0001",
                "subject_id": "SYN-PERSON-001",
                "nested": {"Email": "generated-person@example.invalid"},
                "outcome": "reconciled",
            },
            key=redaction_key,
        ),
        "telemetry": metrics.summary(),
    }
    return {
        "reference_kind": "synthetic_vendor_evaluation",
        "reference_version": REFERENCE_VERSION,
        "runtime_effect": "none",
        "evaluation_id": "VENDOR-EVALUATION-001",
        "intended_use": intended_use_profile["intended_use"],
        "result": result,
        "summary": {
            "vendors": ["sapio", "benchling", "labkey"],
            "vendor_readback_converged": (
                result["telemetry"]["vendor_projection_readback"]["ratio"] == 1.0
            ),
            "migration_semantic_parity": migration_report.semantic_parity,
            "restore_within_recovery_objective": (
                restore_report["observed_recovery_seconds"]
                <= restore_report["recovery_objective_seconds"]
            ),
            "event_delivery_outcome": result["event_delivery"]["outcome"],
            "limitations": [
                "All inputs and vendor endpoints are synthetic.",
                "Results support comparison and planning; accountable decisions remain external.",
            ],
        },
    }


def write_bundle(evaluation: dict[str, Any], output: Path) -> None:
    """Write one portable evaluation document.

    CI can retain this file as an ordinary build artifact. Delivery systems keep
    release records in their established stores.
    """

    output.mkdir(parents=True, exist_ok=True)
    (output / "result.json").write_text(
        json.dumps(evaluation, indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
    )


def _vendor_manifest(record: dict[str, Any]) -> dict[str, Any]:
    return {
        "vendor": record["vendor"],
        "vendor_version": record["vendor_version"],
        "external_id": record["external_id"],
        "content_digest": record["content_digest"],
        "projection": "identity, vendor version, and content digest",
    }


def _event_time(clock: str, offset: int) -> str:
    normalized = clock[:-1] + "+00:00" if clock.endswith("Z") else clock
    value = datetime.fromisoformat(normalized)
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("evaluation clock requires an explicit UTC offset")
    if value.utcoffset() != timedelta(0):
        raise ValueError("evaluation clock requires UTC")
    event_time = value.astimezone(timezone.utc) + timedelta(milliseconds=offset)
    return event_time.isoformat(timespec="milliseconds").replace("+00:00", "Z")


def _validate_intended_use_profile(profile: dict[str, Any]) -> None:
    required = {
        "profile_version",
        "intended_use",
        "runtime_effect",
        "comparison_scope",
        "record_classes",
        "limitations",
    }
    if set(profile) != required:
        raise ValueError("intended-use profile requires the documented field set")
    if profile["profile_version"] != "1.0.0":
        raise ValueError("intended-use profile requires version 1.0.0")
    if profile["runtime_effect"] != "none":
        raise ValueError("intended-use profile requires runtime_effect none")
    if not isinstance(profile["intended_use"], str) or not profile[
        "intended_use"
    ].strip():
        raise ValueError("intended-use profile requires an explicit intended use")
