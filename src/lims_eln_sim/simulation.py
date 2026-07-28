from __future__ import annotations

from dataclasses import asdict
from pathlib import Path
import json
from typing import Any

from .assurance import MetricBook, Principal, authorize, redact_trace
from .configuration import (
    AwsRuntimeReference,
    SyntheticAwsProvider,
    resolve_runtime_configuration,
)
from .domain import Specimen, digest
from .migration import MigrationHarness
from .safety import validate_synthetic_fixture
from .vendors import (
    AmbiguousWrite,
    BenchlingEmulator,
    LabKeyEmulator,
    SapioEmulator,
)


FORECAST_METADATA = {
    "evidence_mode": "simulated",
    "assurance_stage": "specified",
    "simulation_authority": "advisory_only",
    "accountable_observation_required": True,
    "forecast_release": "forecast-2026-Q3-r2",
}


def run(fixture: dict[str, Any], *, redaction_key: bytes) -> dict[str, Any]:
    validate_synthetic_fixture(fixture)
    clock = fixture["clock"]
    specimen = Specimen(
        specimen_id=fixture["specimen_id"],
        tenant_id=fixture["tenant_id"],
        source_alias=fixture["source_alias"],
    )
    transitions = [
        ("accessioned", "accessioner", {"alias": specimen.source_alias}),
        ("in_custody", "courier", {"location": "receiving-freezer-2"}),
        ("instrument_complete", "instrument-gateway", {"run_id": fixture["run_id"]}),
        ("reviewed", "scientist", {"interpretation": fixture["interpretation"]}),
        ("released", "pathologist", {"release_reason": "review-complete"}),
    ]
    specimen.result = fixture["result"]
    specimen.artifact_digest = digest(fixture["artifact"])
    for offset, (status, actor, detail) in enumerate(transitions):
        specimen.transition(status, actor, detail, f"{clock[:-1]}.{offset:03d}Z")

    principal = Principal("svc-projection", fixture["tenant_id"], ("vendor_writer",))
    authorization = authorize(principal, specimen.tenant_id, "vendor_writer")

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
    benchling_record = benchling.write("req-benchling-0001", specimen.specimen_id, specimen.view())
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
    validation = labkey.validate_rows(rows)
    labkey_record = labkey.write("req-labkey-0001", specimen.specimen_id, specimen.view())

    migration = MigrationHarness()
    migrated, migration_report = migration.migrate([specimen.view()])
    _, migration_failure_report = migration.migrate(
        [specimen.view()],
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
    exit_report = migration.data_exit(migrated)
    runtime_configuration = resolve_runtime_configuration(
        AwsRuntimeReference.from_dict(fixture["runtime_configuration"]),
        SyntheticAwsProvider(),
    )

    metrics = MetricBook()
    for record in (sapio_record, benchling_record, benchling_readback, labkey_record):
        metrics.observe("vendor_projection_readback", record["external_id"] == specimen.specimen_id)
    metrics.observe("migration_semantic_parity", migration_report.semantic_parity)
    metrics.observe(
        "restore_within_recovery_objective",
        restore_report["observed_recovery_seconds"] <= restore_report["recovery_objective_seconds"],
    )

    core = {
        "specimen": specimen.view(),
        "authorization": authorization,
        "vendors": {
            "sapio": _vendor_manifest(sapio_record),
            "benchling": {
                "event": benchling_event,
                "authoritative_readback": _vendor_manifest(benchling_readback),
            },
            "labkey": {"validation": validation, "record": _vendor_manifest(labkey_record)},
        },
        "migration": asdict(migration_report),
        "restore": restore_report,
        "data_exit": exit_report,
        "failure_twins": {
            "migration": asdict(migration_failure_report),
            "restore": restore_failure_report,
        },
        "runtime_configuration": runtime_configuration.receipt,
        "security_exercise": {
            "scenario": "trace-redaction",
            "observed": redact_trace(
                {
                    "request_id": "req-sapio-0001",
                    "subject_id": "SYN-PERSON-001",
                    "nested": {"Email": "generated-person@example.invalid"},
                    "outcome": "reconciled",
                },
                key=redaction_key,
            ),
            "replacement_behavior": "protected fields retain classification and keyed pseudonym",
        },
        "telemetry": metrics.summary(),
    }
    return {
        **FORECAST_METADATA,
        "simulation_id": "SIM-FINAL-STATE-001",
        "content_digest": digest(core),
        "result": core,
        "acceptance_drafts": acceptance_drafts(core),
        "receipts": simulated_receipts(core),
    }


def acceptance_drafts(core: dict[str, Any]) -> list[dict[str, Any]]:
    domains = ("scientific", "quality", "regulatory", "security", "operations")
    return [
        {
            **FORECAST_METADATA,
            "acceptance_domain": domain,
            "decision_status": "simulated_resolved",
            "projected_verdict": "accept_with_named_scope",
            "basis_digest": digest(core),
            "accountable_role": f"{domain}_approver",
        }
        for domain in domains
    ]


def simulated_receipts(core: dict[str, Any]) -> list[dict[str, Any]]:
    families = (
        "configured_vendor_environments",
        "representative_migration_and_restore",
        "production_security_and_observability",
        "accountable_scientific_quality_regulatory_acceptance",
    )
    return [
        {
            **FORECAST_METADATA,
            "receipt_id": f"SIM-RECEIPT-{index:03d}",
            "receipt_family": family,
            "claim_scope": "counterfactual final-state behavior",
            "artifact_digest": digest({"family": family, "core": core}),
            "limitations": ["synthetic fixtures", "deterministic emulators", "advisory decisions"],
        }
        for index, family in enumerate(families, start=1)
    ]


def write_bundle(bundle: dict[str, Any], output: Path) -> None:
    output.mkdir(parents=True, exist_ok=True)
    documents = {
        "result.json": bundle,
        "migration-report.json": bundle["result"]["migration"],
        "restore-report.json": bundle["result"]["restore"],
        "security-exercise.json": bundle["result"]["security_exercise"],
        "telemetry-summary.json": bundle["result"]["telemetry"],
        "acceptance-drafts.json": bundle["acceptance_drafts"],
        "simulated-receipts.json": bundle["receipts"],
    }
    for name, value in documents.items():
        (output / name).write_text(
            json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + "\n",
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
