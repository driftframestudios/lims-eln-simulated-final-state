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


class ReceiptCriteriaError(ValueError):
    """A simulated closure returns to the criterion that still needs evidence."""


def close_open_receipts(
    core: dict[str, Any],
    bounded_caller: dict[str, Any],
) -> list[dict[str, Any]]:
    """Close every receipt inside one declared, self-consistent future reality."""

    vendor = _vendor_environment_closure(core)
    migration = _migration_restore_closure(core)
    security = _security_observability_closure(core, bounded_caller)
    closures = (
        vendor,
        migration,
        security,
        _acceptance_closure(core, (vendor, migration, security)),
    )
    return [_seal(item) for item in closures]


def _base(receipt_id: str, family: str, claim_scope: str) -> dict[str, Any]:
    return {
        "schema_version": "2.0.0",
        "receipt_id": receipt_id,
        "receipt_family": family,
        "evidence_mode": "simulated",
        "assurance_stage": "verified",
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
    specimen_id = core["specimen"]["specimen_id"]
    bindings = [
        {
            "vendor": "sapio",
            "version": vendors["sapio"]["vendor_version"],
            "sdk_band": "sapiopylib-compatible-simulated-band",
            "readback_digest": vendors["sapio"]["content_digest"],
            "conformance": (
                "passed"
                if vendors["sapio"]["external_id"] == specimen_id
                else "failed"
            ),
        },
        {
            "vendor": "benchling",
            "version": vendors["benchling"]["authoritative_readback"][
                "vendor_version"
            ],
            "sdk_band": "benchling-sdk-stable-simulated-band",
            "readback_digest": vendors["benchling"]["authoritative_readback"][
                "content_digest"
            ],
            "conformance": (
                "passed"
                if (
                    vendors["benchling"]["authoritative_readback"]["external_id"]
                    == specimen_id
                    and vendors["benchling"]["event"]["external_id"] == specimen_id
                )
                else "failed"
            ),
        },
        {
            "vendor": "labkey",
            "version": vendors["labkey"]["record"]["vendor_version"],
            "sdk_band": "labkey-python-api-simulated-band",
            "readback_digest": vendors["labkey"]["record"]["content_digest"],
            "conformance": (
                "passed"
                if (
                    vendors["labkey"]["record"]["external_id"] == specimen_id
                    and vendors["labkey"]["validation"]["valid"] is True
                )
                else "failed"
            ),
        },
    ]
    checks = {
        "task_scoped_configuration": (
            core["runtime_configuration"]["provider_contract"]
            == "aws-ssm-and-secrets-manager"
        ),
        "authoritative_identity_readback": all(
            binding["conformance"] == "passed" for binding in bindings
        ),
        "ambiguous_write_reconciled": vendors["sapio"]["external_id"] == specimen_id,
        "version_bands_retained": all(
            isinstance(binding["version"], str) and bool(binding["version"])
            for binding in bindings
        ),
    }
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
            "vendor_bindings": bindings,
            "checks": checks,
            "outcome": "passed" if all(checks.values()) else "failed",
        }
    )
    return receipt


def _migration_restore_closure(core: dict[str, Any]) -> dict[str, Any]:
    checks = {
        "representative_record_count": core["migration_corpus"]["record_count"] >= 4,
        "representative_artifact_count": core["migration_corpus"]["artifact_count"]
        >= 3,
        "semantic_parity": core["migration"]["semantic_parity"],
        "rollback_ready": core["migration"]["rollback_ready"],
        "clean_environment": core["restore"]["clean_environment"],
        "readback_parity": core["restore"]["readback_parity"],
        "recovery_objective_met": core["restore"]["recovery_objective_met"],
        "data_exit_reconstructable": core["data_exit"]["reconstructable"],
        "migration_failure_twin_detected": bool(
            core["failure_twins"]["migration"]["mismatch_paths"]
        )
        and not core["failure_twins"]["migration"]["semantic_parity"],
        "restore_failure_twin_detected": not core["failure_twins"]["restore"][
            "qualification_ready"
        ],
    }
    receipt = _base(
        "SIM-CLOSED-MIGRATION-001",
        RECEIPT_FAMILIES[1],
        "Representative migration, clean restore, rollback, and data-exit rehearsal",
    )
    receipt.update(
        {
            "corpus": {
                "fixture_class": "representative_synthetic",
                "fixture_digest": core["migration_corpus"]["fixture_digest"],
                "record_count": core["migration_corpus"]["record_count"],
                "artifact_count": core["migration_corpus"]["artifact_count"],
                "source_digest": core["migration"]["source_digest"],
                "target_digest": core["migration"]["target_digest"],
            },
            "checks": {
                **checks,
                "recovery_objective_seconds": core["restore"][
                    "recovery_objective_seconds"
                ],
                "observed_recovery_seconds": core["restore"][
                    "observed_recovery_seconds"
                ],
            },
            "outcome": "passed" if all(checks.values()) else "failed",
        }
    )
    return receipt


def _security_observability_closure(
    core: dict[str, Any],
    bounded_caller: dict[str, Any],
) -> dict[str, Any]:
    metrics = core["telemetry"]
    required_scenarios = {
        "approval_required",
        "cross_tenant",
        "unreleased_operation",
    }
    observed_scenarios = {
        item["scenario"] for item in bounded_caller["bounded_scenarios"]
    }
    protected_trace = core["security_exercise"]["observed"]
    checks = {
        "tenant_boundary": core["authorization"]["decision"] == "allow",
        "protected_trace_projection": (
            protected_trace["subject_id"]["classification"] == "protected"
            and protected_trace["nested"]["Email"]["classification"] == "protected"
        ),
        "parameter_store_reference": bool(
            core["runtime_configuration"]["parameter_versions"]
        ),
        "credential_store_reference": bool(
            core["runtime_configuration"]["secret_reference_digests"]
        ),
        "vendor_readback_sli": metrics["vendor_projection_readback"]["valid"] > 0
        and metrics["vendor_projection_readback"]["ratio"] == 1.0,
        "migration_parity_sli": metrics["migration_semantic_parity"]["valid"] > 0
        and metrics["migration_semantic_parity"]["ratio"] == 1.0,
        "bounded_caller_failure_twins": observed_scenarios == required_scenarios,
        "broad_write_approval_bound": bounded_caller["summary"][
            "broad_write_approval_bound"
        ]
        is True,
    }
    receipt = _base(
        "SIM-CLOSED-SECURITY-001",
        RECEIPT_FAMILIES[2],
        "Production-shape security, secret lifecycle, observability, and recovery exercise",
    )
    receipt.update(
        {
            "checks": {
                **checks,
                "rotation_posture": core["runtime_configuration"]["rotation_behavior"],
                "bounded_caller": bounded_caller["summary"],
            },
            "failure_twins": [
                item["scenario"] for item in bounded_caller["bounded_scenarios"]
            ],
            "outcome": "passed" if all(checks.values()) else "failed",
        }
    )
    return receipt


def _acceptance_closure(
    core: dict[str, Any],
    prerequisite_receipts: tuple[dict[str, Any], ...],
) -> dict[str, Any]:
    receipt = _base(
        "SIM-CLOSED-ACCEPTANCE-001",
        RECEIPT_FAMILIES[3],
        "Independent Scientific, Quality, and Regulatory acceptance in the selected future",
    )
    profile = core["intended_use_profile"]
    basis_digest = digest(
        {
            "core": core,
            "intended_use_profile": profile,
            "prerequisite_receipts": [
                {
                    "receipt_family": item["receipt_family"],
                    "outcome": item["outcome"],
                }
                for item in prerequisite_receipts
            ],
        }
    )
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
            "checks": {
                "intended_use_released": profile["profile_version"] == "1.0.0",
                "simulated_evidence_declared": profile["evidence_mode"]
                == "simulated",
                "prerequisite_receipts_passed": all(
                    item["outcome"] == "passed"
                    for item in prerequisite_receipts
                ),
                "distinct_accountable_domains": len(
                    {item["domain"] for item in decisions}
                )
                == 3,
                "shared_basis": len(
                    {item["basis_digest"] for item in decisions}
                )
                == 1,
            },
            "independence": {
                "mode": "distinct_simulated_accountable_roles",
                "role_count": len(decisions),
                "shared_basis_digest": basis_digest,
            },
            "residual_risk_disposition": "accepted_within_selected_future_reality",
            "outcome": "passed",
        }
    )
    receipt["outcome"] = (
        "passed" if all(receipt["checks"].values()) else "failed"
    )
    return receipt


def _seal(receipt: dict[str, Any]) -> dict[str, Any]:
    if receipt.get("outcome") != "passed":
        failed = sorted(
            name
            for name, result in (receipt.get("checks") or {}).items()
            if isinstance(result, bool) and not result
        )
        raise ReceiptCriteriaError(
            f"receipt family {receipt['receipt_family']!r} requires evidence for "
            + ", ".join(failed or ["released closure criteria"])
        )
    closed = {
        **receipt,
        "closure_status": "closed_in_simulation",
    }
    return {
        **closed,
        "closure_digest": digest(closed),
    }
