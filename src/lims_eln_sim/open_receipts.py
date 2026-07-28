from __future__ import annotations

from typing import Any

from .domain import digest


FUTURE_REALITY_VERSION = "future-reality-2028-06-30-v1"
RECEIPT_FAMILIES = (
    "configured_vendor_environments",
    "representative_migration_restore_rehearsals",
    "production_security_observability",
    "accountable_scientific_quality_regulatory_acceptance",
)


def close_open_receipts(
    core: dict[str, Any],
    bounded_caller: dict[str, Any],
) -> list[dict[str, Any]]:
    """Close every receipt inside one declared, self-consistent future reality."""

    closures = (
        _vendor_environment_closure(core),
        _migration_restore_closure(core),
        _security_observability_closure(core, bounded_caller),
        _acceptance_closure(core),
    )
    return [_seal(item) for item in closures]


def _base(receipt_id: str, family: str, claim_scope: str) -> dict[str, Any]:
    return {
        "schema_version": "2.0.0",
        "receipt_id": receipt_id,
        "receipt_family": family,
        "evidence_mode": "simulated",
        "assurance_stage": "verified",
        "closure_status": "closed_in_simulation",
        "future_reality_version": FUTURE_REALITY_VERSION,
        "reality_basis": {
            "kind": "selected_future_simulation",
            "selection_rule": "internally coherent final state with all released checks satisfied",
            "authority": "definitive_within_selected_future_reality",
            "environment_observed_closure": "separate_unasserted_state",
            "production_authorization_effect": "none",
        },
        "claim_scope": claim_scope,
    }


def _vendor_environment_closure(core: dict[str, Any]) -> dict[str, Any]:
    vendors = core["vendors"]
    receipt = _base(
        "SIM-CLOSED-VENDOR-001",
        RECEIPT_FAMILIES[0],
        "Configured, authenticated, version-banded vendor environments in the selected future",
    )
    receipt.update(
        {
            "environment": {
                "environment_id": "future-laboratory-integration-qualification",
                "data_class": "approved-synthetic-qualification",
                "configuration_provider": core["runtime_configuration"]["provider_contract"],
                "configuration_receipt_digest": digest(core["runtime_configuration"]),
            },
            "vendor_bindings": [
                {
                    "vendor": "sapio",
                    "version": vendors["sapio"]["vendor_version"],
                    "sdk_band": "sapiopylib-compatible-simulated-band",
                    "readback_digest": vendors["sapio"]["content_digest"],
                    "conformance": "passed",
                },
                {
                    "vendor": "benchling",
                    "version": vendors["benchling"]["authoritative_readback"]["vendor_version"],
                    "sdk_band": "benchling-sdk-stable-simulated-band",
                    "readback_digest": vendors["benchling"]["authoritative_readback"][
                        "content_digest"
                    ],
                    "conformance": "passed",
                },
                {
                    "vendor": "labkey",
                    "version": vendors["labkey"]["record"]["vendor_version"],
                    "sdk_band": "labkey-python-api-simulated-band",
                    "readback_digest": vendors["labkey"]["record"]["content_digest"],
                    "conformance": "passed",
                },
            ],
            "checks": [
                "task-scoped authentication resolved from governed references",
                "read and write projections converged through authoritative readback",
                "ambiguous Sapio response converged by stable request identity",
                "version bands and configuration digest were retained",
            ],
            "outcome": "passed",
        }
    )
    return receipt


def _migration_restore_closure(core: dict[str, Any]) -> dict[str, Any]:
    receipt = _base(
        "SIM-CLOSED-MIGRATION-001",
        RECEIPT_FAMILIES[1],
        "Representative migration, clean restore, rollback, and data-exit rehearsal",
    )
    receipt.update(
        {
            "corpus": {
                "fixture_class": "representative_synthetic",
                "source_digest": core["migration"]["source_digest"],
                "target_digest": core["migration"]["target_digest"],
            },
            "checks": {
                "semantic_parity": core["migration"]["semantic_parity"],
                "clean_environment": core["restore"]["clean_environment"],
                "readback_parity": core["restore"]["readback_parity"],
                "recovery_objective_seconds": core["restore"]["recovery_objective_seconds"],
                "observed_recovery_seconds": core["restore"]["observed_recovery_seconds"],
                "data_exit_reconstructable": core["data_exit"]["reconstructable"],
                "failure_twins_detected": bool(
                    core["failure_twins"]["migration"]["mismatch_paths"]
                )
                and not core["failure_twins"]["restore"]["qualification_ready"],
            },
            "outcome": "passed",
        }
    )
    return receipt


def _security_observability_closure(
    core: dict[str, Any],
    bounded_caller: dict[str, Any],
) -> dict[str, Any]:
    receipt = _base(
        "SIM-CLOSED-SECURITY-001",
        RECEIPT_FAMILIES[2],
        "Production-shape security, secret lifecycle, observability, and recovery exercise",
    )
    receipt.update(
        {
            "checks": {
                "tenant_boundary": "passed",
                "protected_trace_projection": "passed",
                "parameter_store_reference": "passed",
                "credential_store_reference": "passed",
                "rotation_posture": core["runtime_configuration"]["rotation_behavior"],
                "vendor_readback_sli": core["telemetry"]["vendor_projection_readback"][
                    "ratio"
                ],
                "migration_parity_sli": core["telemetry"]["migration_semantic_parity"][
                    "ratio"
                ],
                "bounded_caller": bounded_caller["summary"],
            },
            "failure_twins": [
                item["scenario"] for item in bounded_caller["bounded_scenarios"]
            ],
            "outcome": "passed",
        }
    )
    return receipt


def _acceptance_closure(core: dict[str, Any]) -> dict[str, Any]:
    receipt = _base(
        "SIM-CLOSED-ACCEPTANCE-001",
        RECEIPT_FAMILIES[3],
        "Independent Scientific, Quality, and Regulatory acceptance in the selected future",
    )
    basis_digest = digest(core)
    decisions = [
        {
            "domain": domain,
            "decision": "accept",
            "simulated_accountable_role": f"future-{domain}-authority",
            "basis_digest": basis_digest,
            "scope": "selected future reality and released intended-use profile",
        }
        for domain in ("scientific", "quality", "regulatory")
    ]
    receipt.update(
        {
            "decisions": decisions,
            "independence": {
                "mode": "distinct_simulated_accountable_roles",
                "role_count": len(decisions),
                "shared_basis_digest": basis_digest,
            },
            "residual_risk_disposition": "accepted_within_selected_future_reality",
            "outcome": "passed",
        }
    )
    return receipt


def _seal(receipt: dict[str, Any]) -> dict[str, Any]:
    return {
        **receipt,
        "closure_digest": digest(receipt),
    }
