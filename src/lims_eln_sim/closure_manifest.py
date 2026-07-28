from __future__ import annotations

from typing import Any

from .domain import digest
from .open_receipts import FUTURE_REALITY_VERSION


FUTURE_REALITY_ID = "FUTURE-REALITY-LIMS-2028-001"
SOURCE_COORDINATES = (
    {
        "release": "seed-forecast-2026-Q3-r2",
        "commit": "6194a1c3911a97aa5e29b1861819a55554019488",
        "digest": "sha256:35b3d9bcadea3ab95b9cf6f3bb26fd95049147f7fcc771815ff71060fae0937a",
    },
    {
        "release": "seed-implementation-v0.2.0",
        "commit": "c79f8727963a427164a11eacb14837d795cd757d",
        "digest": "sha256:3e9079af08ae3c153a8eebb438fb342ffd6313c34c0a53247e9f9c6b054d0494",
    },
)


def build_governance_closure(
    core: dict[str, Any],
    receipts: list[dict[str, Any]],
) -> dict[str, Any]:
    """Project executable results into the governance 2.0 closure contract."""

    by_family = {receipt["receipt_family"]: receipt for receipt in receipts}
    projections = [
        _vendor_projection(by_family["configured_vendor_environments"]),
        _migration_projection(
            by_family["representative_migration_restore_rehearsals"]
        ),
        _security_projection(by_family["production_security_observability"]),
        _acceptance_projection(
            by_family["accountable_scientific_quality_regulatory_acceptance"]
        ),
    ]
    artifact_ids = [
        projection["artifacts"][0]["artifact_id"] for projection in projections
    ]
    aggregate_digest = digest(
        {
            "future_reality_version": FUTURE_REALITY_VERSION,
            "content_digest": digest(core),
            "receipt_digests": [
                projection["artifacts"][0]["digest"] for projection in projections
            ],
        }
    )
    return {
        "closure_id": "CLOSURE-SIM-SUBSTANTIVE-2028-V1",
        "future_reality": {
            "future_reality_id": FUTURE_REALITY_ID,
            "as_of": "2028-06-30",
            "narrative": (
                "This selected future reality models a fully configured multi-vendor "
                "LIMS and ELN service whose migration, recovery, security, "
                "observability, and role-separated acceptance paths complete through "
                "released executable contracts and representative synthetic evidence."
            ),
            "assumption_ids": [
                "ASSUMPTION-VENDOR-BANDS-2028",
                "ASSUMPTION-REPRESENTATIVE-CORPUS-2028",
                "ASSUMPTION-MODELED-AUTHORITY-2028",
            ],
            "source_coordinates": list(SOURCE_COORDINATES),
            "modeled_authority_roles": [
                "Scientific authority",
                "Quality authority",
                "Regulatory authority",
                "Security and privacy authority",
                "Operational authority",
            ],
        },
        "evidence_mode": "simulated",
        "closure_status": "closed_in_simulation",
        "environment_observed_closure": "separate_unasserted_state",
        "production_authorization_effect": "none",
        "receipt_closures": projections,
        "executable_checks": [
            {
                "check_id": f"CHECK-{check_suffix}",
                "command": [
                    "env",
                    "PYTHONPATH=src",
                    "python3",
                    "-m",
                    "lims_eln_sim.receipt_checks",
                    receipt_family,
                ],
                "working_directory": "lims-eln-simulated-final-state",
                "expected_exit_code": 0,
                "artifact_ids": [artifact_id],
            }
            for (check_suffix, receipt_family), artifact_id in zip(
                (
                    (
                        "CONFIGURED-VENDORS",
                        "configured_vendor_environments",
                    ),
                    (
                        "MIGRATION-RESTORE",
                        "representative_migration_restore_rehearsals",
                    ),
                    (
                        "SECURITY-OBSERVABILITY",
                        "production_security_observability",
                    ),
                    (
                        "ACCOUNTABLE-ACCEPTANCE",
                        "accountable_scientific_quality_regulatory_acceptance",
                    ),
                ),
                artifact_ids,
                strict=True,
            )
        ],
        "aggregate_outcome": {
            "result": "passed",
            "closed_family_count": len(projections),
            "expected_family_count": 4,
            "reproduction_statement": (
                "The four declared commands regenerate and verify each closure family "
                "from the pinned synthetic fixture, bounded-caller policy, and selected "
                "future-reality assumptions."
            ),
        },
        "aggregate_artifacts": [
            {
                "artifact_id": "ARTIFACT-SIM-SUBSTANTIVE-CLOSURE-2028-V1",
                "media_type": "application/json",
                "digest": aggregate_digest,
                "locator": "evidence://simulation/closures/substantive-2028-v1",
                "sensitivity": "internal",
                "retention_class": "simulation-baseline",
            }
        ],
        "limitations": [
            (
                "The four families are closed inside the selected future reality; "
                "environment-observed closure remains a separate unasserted state."
            ),
            (
                "Modeled authority roles establish a complete decision shape and grant "
                "no production authorization."
            ),
        ],
        "divergence_triggers": [
            (
                "A released contract, selected-future assumption, representative "
                "fixture, vendor behavior band, or modeled authority policy changes."
            ),
            (
                "A regenerated family artifact differs from its retained digest or a "
                "bounded-caller failure twin produces an authorized effect."
            ),
        ],
        "metadata": {
            "schema_version": "2.0.0",
            "created_at": "2026-07-28T18:45:00Z",
            "updated_at": "2026-07-28T18:45:00Z",
            "owner": {
                "actor_id": "OWNER-SIMULATION-CLOSURE",
                "display_name": "Simulation stewardship role",
                "role": "Future-reality closure stewardship",
            },
        },
    }


def _artifact(
    artifact_id: str,
    locator: str,
    receipt: dict[str, Any],
    *,
    sensitivity: str = "internal",
) -> dict[str, Any]:
    return {
        "artifact_id": artifact_id,
        "media_type": "application/json",
        "digest": receipt["closure_digest"],
        "locator": locator,
        "sensitivity": sensitivity,
        "retention_class": "simulation-baseline",
    }


def _environment(
    environment_id: str,
    environment_class: str,
    configuration_digest: str,
    schema_version: str,
    *,
    vendor_build: str | None = None,
) -> dict[str, Any]:
    value = {
        "environment_id": environment_id,
        "class": environment_class,
        "region": "synthetic-us-east",
        "configuration_digest": configuration_digest,
        "schema_version": schema_version,
    }
    if vendor_build is not None:
        value["vendor_build"] = vendor_build
    return value


def _vendor_projection(receipt: dict[str, Any]) -> dict[str, Any]:
    return {
        "simulated_receipt_id": "RECEIPT-SIM-CONFIGURED-VENDORS-2028-V1",
        "family": "configured_vendor_environments",
        "claim": (
            "Sapio, Benchling, and LabKey adapters complete released read, "
            "idempotent-write, replay, recovery, and bounded-caller scenarios."
        ),
        "scope": (
            "Synthetic research-use specimen and evidence projections across "
            "version-banded future vendor environments."
        ),
        "scenario_ids": [
            "SCENARIO-VENDOR-READ",
            "SCENARIO-VENDOR-NARROW-WRITE",
            "SCENARIO-AMBIGUOUS-WRITE",
        ],
        "test_ids": [
            "TEST-SAPIO-CONFORMANCE",
            "TEST-BENCHLING-CONFORMANCE",
            "TEST-LABKEY-CONFORMANCE",
        ],
        "simulated_environment": _environment(
            "ENV-SIM-VENDORS-2028-V1",
            "vendor_sandbox",
            receipt["environment"]["configuration_receipt_digest"],
            "vendor-contract-3.0",
            vendor_build="selected-future-vendor-band-2028",
        ),
        "outcome": "passed",
        "closure_statement": (
            "Every configured-vendor criterion is closed inside "
            f"{FUTURE_REALITY_ID}."
        ),
        "artifacts": [
            _artifact(
                "ARTIFACT-SIM-VENDOR-CONFORMANCE-2028-V1",
                "evidence://simulation/closures/configured-vendors-2028-v1",
                receipt,
            )
        ],
        "modeled_authority_roles": [
            "Vendor qualification authority",
            "Scientific data authority",
        ],
        "limitations": [
            "Vendor tenants, identities, and version bands are executable simulation fixtures."
        ],
    }


def _migration_projection(receipt: dict[str, Any]) -> dict[str, Any]:
    return {
        "simulated_receipt_id": "RECEIPT-SIM-MIGRATION-RESTORE-2028-V1",
        "family": "representative_migration_restore_rehearsals",
        "claim": (
            "Representative migration, clean restore, rollback, and data-exit "
            "rehearsals preserve meaning and satisfy the selected recovery objective."
        ),
        "scope": (
            "A representative synthetic laboratory corpus with scientific results, "
            "lineage, artifacts, and explicit failure twins."
        ),
        "scenario_ids": [
            "SCENARIO-MIGRATION-PARITY",
            "SCENARIO-CLEAN-RESTORE",
            "SCENARIO-DATA-EXIT",
        ],
        "test_ids": [
            "TEST-MIGRATION-RECONCILIATION",
            "TEST-RESTORE-CONTINUITY",
            "TEST-FAILURE-TWINS",
        ],
        "simulated_environment": _environment(
            "ENV-SIM-MIGRATION-2028-V1",
            "qualification",
            digest(receipt["corpus"]),
            "migration-contract-3.0",
        ),
        "outcome": "passed",
        "closure_statement": (
            "Every representative migration and restore criterion is closed inside "
            f"{FUTURE_REALITY_ID}."
        ),
        "artifacts": [
            _artifact(
                "ARTIFACT-SIM-MIGRATION-RESTORE-2028-V1",
                "evidence://simulation/closures/migration-restore-2028-v1",
                receipt,
            )
        ],
        "modeled_authority_roles": [
            "Migration authority",
            "Continuity authority",
        ],
        "limitations": [
            "Recovery timing and throughput derive from deterministic future-reality models."
        ],
    }


def _security_projection(receipt: dict[str, Any]) -> dict[str, Any]:
    return {
        "simulated_receipt_id": "RECEIPT-SIM-SECURITY-OBSERVABILITY-2028-V1",
        "family": "production_security_observability",
        "claim": (
            "Production-shaped identity, tenant isolation, AWS configuration and "
            "credential references, telemetry, and bounded-caller controls satisfy "
            "the selected future control profile."
        ),
        "scope": (
            "Synthetic tenant workloads, AWS Parameter Store and Secrets Manager "
            "references, protected traces, vendor readback signals, and failure twins."
        ),
        "scenario_ids": [
            "SCENARIO-CROSS-TENANT-BLOCK",
            "SCENARIO-APPROVAL-BOUND-WRITE",
            "SCENARIO-UNRELEASED-OPERATION",
        ],
        "test_ids": [
            "TEST-SECURITY-CONTROLS",
            "TEST-OBSERVABILITY-SIGNALS",
            "TEST-BOUNDED-CALLER",
        ],
        "simulated_environment": _environment(
            "ENV-SIM-PRODUCTION-2028-V1",
            "production",
            digest(receipt["checks"]),
            "runtime-control-profile-3.0",
        ),
        "outcome": "passed",
        "closure_statement": (
            "Every production-shaped security and observability criterion is closed "
            f"inside {FUTURE_REALITY_ID}."
        ),
        "artifacts": [
            _artifact(
                "ARTIFACT-SIM-SECURITY-OBSERVABILITY-2028-V1",
                "evidence://simulation/closures/security-observability-2028-v1",
                receipt,
                sensitivity="confidential",
            )
        ],
        "modeled_authority_roles": [
            "Security and privacy authority",
            "Operational authority",
        ],
        "limitations": [
            "The production class describes a future-reality topology and retains simulated evidence mode."
        ],
    }


def _acceptance_projection(receipt: dict[str, Any]) -> dict[str, Any]:
    return {
        "simulated_receipt_id": "RECEIPT-SIM-ACCOUNTABLE-ACCEPTANCE-2028-V1",
        "family": "accountable_scientific_quality_regulatory_acceptance",
        "claim": (
            "Separate modeled Scientific, Quality, and Regulatory authorities accept "
            "one immutable evidence basis with explicit scope and residual-risk posture."
        ),
        "scope": (
            "The selected future research-use lifecycle, vendor integrations, "
            "migration, recovery, security, observability, and retained evidence."
        ),
        "scenario_ids": [
            "SCENARIO-SCIENTIFIC-ACCEPTANCE",
            "SCENARIO-QUALITY-ACCEPTANCE",
            "SCENARIO-REGULATORY-ACCEPTANCE",
        ],
        "test_ids": [
            "TEST-SCIENTIFIC-PACKET",
            "TEST-QUALITY-PACKET",
            "TEST-REGULATORY-PACKET",
        ],
        "simulated_environment": _environment(
            "ENV-SIM-ACCEPTANCE-2028-V1",
            "qualification",
            receipt["independence"]["shared_basis_digest"],
            "acceptance-packet-3.0",
        ),
        "outcome": "passed",
        "closure_statement": (
            "Every modeled Scientific, Quality, and Regulatory acceptance criterion is "
            f"closed inside {FUTURE_REALITY_ID}."
        ),
        "artifacts": [
            _artifact(
                "ARTIFACT-SIM-ACCOUNTABLE-ACCEPTANCE-2028-V1",
                "evidence://simulation/closures/accountable-acceptance-2028-v1",
                receipt,
            )
        ],
        "modeled_authority_roles": [
            "Scientific authority",
            "Quality authority",
            "Regulatory authority",
        ],
        "limitations": [
            "Authority resides in modeled roles inside the selected future reality and grants no production authorization."
        ],
    }
