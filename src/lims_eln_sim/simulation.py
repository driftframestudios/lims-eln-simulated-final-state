from __future__ import annotations

from dataclasses import asdict
from datetime import datetime, timedelta, timezone
from pathlib import Path
import json
from typing import Any

from .assurance import MetricBook, Principal, authorize, redact_trace
from .bounded_caller import simulate_control_plane
from .configuration import (
    AwsRuntimeReference,
    SyntheticAwsProvider,
    resolve_runtime_configuration,
)
from .closure_manifest import build_governance_closure
from .domain import Specimen, digest
from .migration import MigrationHarness, validate_representative_corpus
from .open_receipts import FUTURE_REALITY_VERSION, close_open_receipts
from .safety import validate_synthetic_fixture
from .vendors import (
    AmbiguousWrite,
    BenchlingEmulator,
    LabKeyEmulator,
    SapioEmulator,
)


FORECAST_METADATA = {
    "evidence_mode": "simulated",
    "assurance_stage": "verified",
    "simulation_authority": "definitive_within_selected_future_reality",
    "accountable_observation_required": False,
    "environment_observed_closure": "separate_unasserted_state",
    "production_authorization_effect": "none",
    "future_reality_version": FUTURE_REALITY_VERSION,
    "forecast_release": "forecast-2028-FR-v1",
}


def run(
    fixture: dict[str, Any],
    *,
    intended_use_profile: dict[str, Any],
    migration_corpus: dict[str, Any],
    redaction_key: bytes,
) -> dict[str, Any]:
    validate_synthetic_fixture(fixture)
    _validate_intended_use_profile(intended_use_profile)
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
        specimen.transition(status, actor, detail, _event_time(clock, offset))

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
    exit_report = migration.data_exit(migrated)
    runtime_configuration = resolve_runtime_configuration(
        AwsRuntimeReference.from_dict(fixture["runtime_configuration"]),
        SyntheticAwsProvider(),
    )
    bounded_caller = simulate_control_plane()

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
        "migration_corpus": {
            "fixture_digest": digest(migration_corpus),
            "record_count": len(representative_records),
            "artifact_count": len(migration_corpus["artifacts"]),
            "exception_classes": list(
                migration_corpus["profile"]["exception_classes"]
            ),
        },
        "intended_use_profile": json.loads(
            json.dumps(
                intended_use_profile,
                sort_keys=True,
                allow_nan=False,
            )
        ),
        "restore": restore_report,
        "data_exit": exit_report,
        "failure_twins": {
            "migration": asdict(migration_failure_report),
            "restore": restore_failure_report,
        },
        "runtime_configuration": runtime_configuration.receipt,
        "bounded_caller": bounded_caller,
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
    receipt_closures = close_open_receipts(core, bounded_caller)
    governance_closure = build_governance_closure(core, receipt_closures)
    return {
        **FORECAST_METADATA,
        "simulation_id": "SIM-FINAL-STATE-001",
        "content_digest": digest(core),
        "result": core,
        "acceptance_drafts": acceptance_drafts(core),
        "receipts": receipt_closures,
        "governance_closure": governance_closure,
        "receipt_closure_summary": {
            "families_expected": 4,
            "families_closed": len(receipt_closures),
            "all_closed": all(
                item["closure_status"] == "closed_in_simulation"
                for item in receipt_closures
            ),
            "future_reality_version": FUTURE_REALITY_VERSION,
        },
    }


def acceptance_drafts(core: dict[str, Any]) -> list[dict[str, Any]]:
    domains = ("scientific", "quality", "regulatory", "security", "operations")
    return [
        {
            **FORECAST_METADATA,
            "acceptance_domain": domain,
            "decision_status": "simulated_resolved",
            "projected_verdict": "accept_selected_future_reality",
            "basis_digest": digest(core),
            "accountable_role": f"future_{domain}_authority",
        }
        for domain in domains
    ]


def simulated_receipts(core: dict[str, Any]) -> list[dict[str, Any]]:
    return close_open_receipts(core, core.get("bounded_caller") or simulate_control_plane())


def closure_bundle(simulation: dict[str, Any]) -> dict[str, Any]:
    """Return the independently reproducible selected-future closure boundary."""

    governance_closure = simulation["governance_closure"]
    return {
        "bundle_version": "2.0.1",
        "future_reality_version": simulation["future_reality_version"],
        "governance_closure_digest": digest(governance_closure),
        "governance_closure": governance_closure,
        "detailed_receipts": simulation["receipts"],
        "source_result_digest": simulation["content_digest"],
    }


def write_bundle(bundle: dict[str, Any], output: Path) -> None:
    output.mkdir(parents=True, exist_ok=True)
    documents = {
        "result.json": bundle,
        "migration-report.json": bundle["result"]["migration"],
        "restore-report.json": bundle["result"]["restore"],
        "security-exercise.json": bundle["result"]["security_exercise"],
        "bounded-caller.json": bundle["result"]["bounded_caller"],
        "telemetry-summary.json": bundle["result"]["telemetry"],
        "acceptance-drafts.json": bundle["acceptance_drafts"],
        "simulated-receipts.json": bundle["receipts"],
        "simulated-receipt-closure.json": bundle["governance_closure"],
        "future-reality-closure-bundle.json": closure_bundle(bundle),
        "receipt-closure-summary.json": bundle["receipt_closure_summary"],
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


def _event_time(clock: str, offset: int) -> str:
    normalized = clock[:-1] + "+00:00" if clock.endswith("Z") else clock
    value = datetime.fromisoformat(normalized)
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("simulation clock requires an explicit UTC offset")
    if value.utcoffset() != timedelta(0):
        raise ValueError("simulation clock requires UTC")
    event_time = value.astimezone(timezone.utc) + timedelta(milliseconds=offset)
    return event_time.isoformat(timespec="milliseconds").replace("+00:00", "Z")


def _validate_intended_use_profile(profile: dict[str, Any]) -> None:
    required = {
        "profile_version",
        "evidence_mode",
        "intended_use",
        "population_cartographies",
        "record_classes",
        "applicability_forks",
        "accountable_determination",
    }
    if set(profile) != required:
        raise ValueError("intended-use profile requires the released field set")
    if profile["profile_version"] != "1.0.0" or profile["evidence_mode"] != "simulated":
        raise ValueError(
            "intended-use profile requires the released simulated 1.0.0 contract"
        )
    if not isinstance(profile["intended_use"], str) or not profile["intended_use"].strip():
        raise ValueError("intended-use profile requires an explicit intended use")
    required_populations = {"scientists", "pathologists", "quality", "regulatory"}
    if not required_populations.issubset(set(profile["population_cartographies"])):
        raise ValueError(
            "intended-use profile requires scientific, pathology, Quality, and Regulatory populations"
        )
