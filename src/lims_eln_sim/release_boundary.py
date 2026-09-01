"""Cross-carrier invariants for the selected-future release."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from .domain import digest


class ReleaseBoundaryError(ValueError):
    """Release carriers return to one selected-future evidence posture."""


def validate_release_alignment(
    *,
    forecast_metadata: Mapping[str, Any],
    governance_closure: Mapping[str, Any],
    detailed_receipts: Sequence[Mapping[str, Any]],
    assumptions_ledger: Mapping[str, Any],
    release_manifest: Mapping[str, Any],
    first_receipt: Mapping[str, Any],
    machine_node: Mapping[str, Any],
) -> None:
    """Bind release carriers to the executable selected-future authority."""

    future = _object(governance_closure.get("future_reality"), "governance future")
    future_reality_id = _text(
        future.get("future_reality_id"),
        "governance future reality id",
    )
    ledger_assumptions = _object_sequence(
        assumptions_ledger.get("assumptions"),
        "assumption ledger entries",
    )
    ledger_assumption_ids = _unique_strings(
        [item.get("assumption_id") for item in ledger_assumptions],
        "assumption ledger IDs",
    )
    closure_assumption_ids = _unique_strings(
        future.get("assumption_ids"),
        "governance selected-future assumption IDs",
    )
    _equal(
        closure_assumption_ids,
        ledger_assumption_ids,
        "governance selected-future assumption IDs",
    )

    future_reality_version = _text(
        forecast_metadata.get("future_reality_version"),
        "forecast future reality version",
    )
    simulation_authority = _text(
        forecast_metadata.get("simulation_authority"),
        "forecast simulation authority",
    )
    evidence_mode = _text(
        forecast_metadata.get("evidence_mode"),
        "forecast evidence mode",
    )
    assurance_stage = _text(
        forecast_metadata.get("assurance_stage"),
        "forecast assurance stage",
    )
    environment_observed_closure = _text(
        forecast_metadata.get("environment_observed_closure"),
        "forecast observed-closure posture",
    )
    production_authorization_effect = _text(
        forecast_metadata.get("production_authorization_effect"),
        "forecast production-authorization effect",
    )
    forecast_release = _text(
        forecast_metadata.get("forecast_release"),
        "forecast release",
    )
    accountable_observation_required = forecast_metadata.get(
        "accountable_observation_required"
    )
    if not isinstance(accountable_observation_required, bool):
        raise ReleaseBoundaryError(
            "forecast accountable-observation posture carries one boolean"
        )

    selected_future_expectations = {
        "future_reality_id": future_reality_id,
        "future_reality_version": future_reality_version,
        "forecast_release": forecast_release,
        "assumption_ids": ledger_assumption_ids,
    }
    for field, expected in (
        ("future_reality_id", future_reality_id),
        ("future_reality_version", future_reality_version),
        ("authority", simulation_authority),
        ("production_authorization_effect", production_authorization_effect),
    ):
        _equal(
            assumptions_ledger.get(field),
            expected,
            f"assumption ledger {field}",
        )
    for index, assumption in enumerate(ledger_assumptions):
        _equal(
            assumption.get("evidence_mode"),
            evidence_mode,
            f"assumptions[{index}] evidence mode",
        )

    for field, expected in (
        ("evidence_mode", evidence_mode),
        ("environment_observed_closure", environment_observed_closure),
        ("production_authorization_effect", production_authorization_effect),
    ):
        _equal(
            governance_closure.get(field),
            expected,
            f"governance closure {field}",
        )
    closure_status = _text(
        governance_closure.get("closure_status"),
        "governance closure status",
    )

    if not detailed_receipts:
        raise ReleaseBoundaryError(
            "detailed receipts carry the selected-future evidence posture"
        )
    for index, receipt in enumerate(detailed_receipts):
        for field, expected in (
            ("evidence_mode", evidence_mode),
            ("assurance_stage", assurance_stage),
            ("closure_status", closure_status),
            ("future_reality_version", future_reality_version),
        ):
            _equal(
                receipt.get(field),
                expected,
                f"detailed receipts[{index}] {field}",
            )
        reality_basis = _object(
            receipt.get("reality_basis"),
            f"detailed receipts[{index}] reality basis",
        )
        for field, expected in (
            ("authority", simulation_authority),
            ("environment_observed_closure", environment_observed_closure),
            ("production_authorization_effect", production_authorization_effect),
        ):
            _equal(
                reality_basis.get(field),
                expected,
                f"detailed receipts[{index}] reality basis {field}",
            )

    _equal(
        release_manifest.get("external_release"),
        forecast_release,
        "release manifest forecast release",
    )
    _equal(
        release_manifest.get("authority_posture"),
        simulation_authority,
        "release manifest authority posture",
    )
    _equal(
        release_manifest.get("reference_closure_digest"),
        digest(dict(governance_closure)),
        "release manifest governance closure digest",
    )
    expected_first_receipt_contract = {
        "evidence_mode": evidence_mode,
        "assurance_stage": assurance_stage,
        "simulation_authority": simulation_authority,
        "accountable_observation_required": accountable_observation_required,
        "closure_status": closure_status,
        "environment_observed_closure": environment_observed_closure,
        "production_authorization_effect": production_authorization_effect,
        "future_reality_version": future_reality_version,
    }
    _equal(
        release_manifest.get("first_receipt_contract"),
        expected_first_receipt_contract,
        "release manifest first-receipt contract",
    )

    first_selected_future = _object(
        first_receipt.get("selected_future"),
        "first receipt selected future",
    )
    first_selected_ids = _unique_strings(
        first_selected_future.get("assumption_ids"),
        "first receipt selected-future assumption IDs",
    )
    first_selected_future = dict(first_selected_future)
    first_selected_future["assumption_ids"] = first_selected_ids
    _equal(
        first_selected_future,
        selected_future_expectations,
        "first receipt selected future",
    )
    authority_posture = _object(
        first_receipt.get("authority_posture"),
        "first receipt authority posture",
    )
    for field, expected in (
        ("mode", "orientation_only"),
        ("simulation_authority", simulation_authority),
        ("accountable_observation_required", accountable_observation_required),
        ("environment_observed_closure", environment_observed_closure),
        ("production_authorization_effect", production_authorization_effect),
    ):
        _equal(
            authority_posture.get(field),
            expected,
            f"first receipt authority posture {field}",
        )
    _text(
        authority_posture.get("statement"),
        "first receipt authority statement",
    )

    evidence_posture = _object_sequence(
        first_receipt.get("evidence_posture"),
        "first receipt evidence posture",
    )
    simulated_evidence = [
        item for item in evidence_posture if item.get("mode") == evidence_mode
    ]
    if not simulated_evidence:
        raise ReleaseBoundaryError(
            "first receipt carries active simulated evidence posture"
        )
    for index, item in enumerate(simulated_evidence):
        _equal(
            item.get("assurance_stage"),
            assurance_stage,
            f"first receipt simulated evidence[{index}] assurance stage",
        )
        _equal(
            item.get("status"),
            "active",
            f"first receipt simulated evidence[{index}] status",
        )
    observed_evidence = [
        item for item in evidence_posture if item.get("mode") == "observed"
    ]
    if not observed_evidence:
        raise ReleaseBoundaryError(
            "first receipt carries the retained observed-evidence path"
        )
    for index, item in enumerate(observed_evidence):
        _equal(
            item.get("assurance_stage"),
            "specified",
            f"first receipt observed evidence[{index}] assurance stage",
        )
        _equal(
            item.get("status"),
            "designed_but_unexercised",
            f"first receipt observed evidence[{index}] status",
        )

    _equal(
        first_receipt.get("first_receipt_id"),
        machine_node.get("first_receipt_contract_id"),
        "first receipt identity",
    )
    _equal(
        first_receipt.get("open_receipts"),
        machine_node.get("open_receipts"),
        "first receipt open-receipt route",
    )
    closure_contracts = [
        item
        for item in _object_sequence(
            first_receipt.get("contract_state"),
            "first receipt contract state",
        )
        if item.get("contract_id") == "SIMULATED-SUBSTANTIVE-CLOSURE-2028-V1"
    ]
    if len(closure_contracts) != 1:
        raise ReleaseBoundaryError(
            "first receipt carries one simulated substantive closure contract"
        )
    _equal(
        closure_contracts[0].get("digest"),
        digest(dict(governance_closure)),
        "first receipt governance closure digest",
    )
    handoff = _object(first_receipt.get("handoff"), "first receipt handoff")
    _equal(
        handoff.get("recipient_role"),
        "comparative evidence stewardship",
        "first receipt next receiver",
    )


def _object(value: Any, label: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise ReleaseBoundaryError(f"{label} carries one object")
    return value


def _object_sequence(value: Any, label: str) -> list[Mapping[str, Any]]:
    if not isinstance(value, list) or not all(
        isinstance(item, Mapping) for item in value
    ):
        raise ReleaseBoundaryError(f"{label} carries an object list")
    return value


def _unique_strings(value: Any, label: str) -> list[str]:
    if not isinstance(value, list) or not value or not all(
        isinstance(item, str) and item.strip() for item in value
    ):
        raise ReleaseBoundaryError(f"{label} carries a non-empty identifier list")
    if len(value) != len(set(value)):
        duplicates = sorted({item for item in value if value.count(item) > 1})
        raise ReleaseBoundaryError(
            f"{label} carries one definition per identifier; duplicates: "
            + ", ".join(duplicates)
        )
    return list(value)


def _text(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ReleaseBoundaryError(f"{label} carries one non-empty value")
    return value


def _equal(actual: Any, expected: Any, label: str) -> None:
    if actual != expected:
        raise ReleaseBoundaryError(
            f"{label} matches the executable selected-future contract"
        )
