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
    bounded_caller: Mapping[str, Any],
    assumptions_ledger: Mapping[str, Any],
    release_manifest: Mapping[str, Any],
    first_receipt: Mapping[str, Any],
    machine_node: Mapping[str, Any],
    coordination_horizon: Mapping[str, Any],
) -> None:
    """Bind release carriers and the living handoff to their current owners."""

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
            ("kind", "selected_future_simulation"),
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
    observed_evidence_present = False
    simulated_evidence_present = False
    for index, item in enumerate(evidence_posture):
        _text(item.get("claim"), f"first receipt evidence posture[{index}] claim")
        mode = _text(
            item.get("mode"),
            f"first receipt evidence posture[{index}] mode",
        )
        if mode == evidence_mode:
            simulated_evidence_present = True
            expected_assurance_stage = assurance_stage
            expected_status = "active"
        elif mode == "observed":
            observed_evidence_present = True
            expected_assurance_stage = "specified"
            expected_status = "designed_but_unexercised"
        else:
            raise ReleaseBoundaryError(
                f"first receipt evidence posture[{index}] mode stays within "
                "the simulated and observed evidence paths"
            )
        _equal(
            item.get("assurance_stage"),
            expected_assurance_stage,
            f"first receipt evidence posture[{index}] assurance stage",
        )
        _equal(
            item.get("status"),
            expected_status,
            f"first receipt evidence posture[{index}] status",
        )
    if not simulated_evidence_present:
        raise ReleaseBoundaryError(
            "first receipt carries active simulated evidence posture"
        )
    if not observed_evidence_present:
        raise ReleaseBoundaryError(
            "first receipt carries the retained observed-evidence path"
        )

    _equal(
        first_receipt.get("first_receipt_id"),
        machine_node.get("first_receipt_contract_id"),
        "first receipt identity",
    )
    _equal(
        first_receipt.get("machine_node_id"),
        machine_node.get("machine_node_id"),
        "first receipt Machine Node identity",
    )
    machine_authority = _object(
        machine_node.get("authority"),
        "Machine Node authority",
    )
    _equal(
        machine_authority.get("mode"),
        "orientation_only",
        "Machine Node authority mode",
    )
    _text(
        machine_node.get("canonical_identity"),
        "Machine Node canonical identity",
    )
    first_open_receipts = _unique_strings(
        first_receipt.get("open_receipts"),
        "first receipt open-receipt IDs",
    )
    machine_open_receipts = _unique_strings(
        machine_node.get("open_receipts"),
        "Machine Node open-receipt IDs",
    )
    _equal(
        first_open_receipts,
        machine_open_receipts,
        "first receipt open-receipt route",
    )
    expected_contracts = {
        "SIMULATED-SUBSTANTIVE-CLOSURE-2028-V1": {
            "version": "2.0.0",
            "digest": digest(dict(governance_closure)),
        },
        "SIMULATION-BOUNDED-CALLER-001": {
            "version": "1.0.0",
            "digest": digest(dict(bounded_caller)),
        },
        "SIMULATED-FAMILY-RECEIPTS-2028-V1": {
            "version": "2.0.0",
            "digest": digest(list(detailed_receipts)),
        },
    }
    first_contracts = _contract_map(
        first_receipt.get("contract_state"),
        "first receipt contract state",
    )
    machine_contracts = _contract_map(
        machine_node.get("contracts"),
        "Machine Node contracts",
    )
    _equal(
        first_contracts,
        expected_contracts,
        "first receipt contract set",
    )
    _equal(
        machine_contracts,
        expected_contracts,
        "Machine Node contract set",
    )
    _equal(
        first_contracts,
        machine_contracts,
        "first receipt and Machine Node contract sets",
    )
    handoff = _object(first_receipt.get("handoff"), "first receipt handoff")
    current_action_ids = _unique_strings(
        coordination_horizon.get("current_item_ids"),
        "Coordination Horizon current item IDs",
    )
    horizon_items = {
        _text(item.get("item_id"), "Coordination Horizon work-item ID"): item
        for item in _object_sequence(
            coordination_horizon.get("work_items"),
            "Coordination Horizon work items",
        )
    }
    if len(current_action_ids) != 1:
        raise ReleaseBoundaryError(
            "first receipt singular recipient resolves through one current "
            "Coordination Horizon item"
        )
    current_item = horizon_items.get(current_action_ids[0])
    if current_item is None:
        raise ReleaseBoundaryError(
            "Coordination Horizon current item resolves to a declared work item"
        )
    _equal(
        handoff.get("recipient_role"),
        current_item.get("owner_role"),
        "first receipt next receiver",
    )
    handoff_action_ids = _unique_strings(
        handoff.get("action_ids"),
        "first receipt handoff action IDs",
    )
    _equal(
        handoff_action_ids,
        current_action_ids,
        "first receipt structured handoff actions",
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


def _contract_map(value: Any, label: str) -> dict[str, dict[str, str]]:
    contracts = _object_sequence(value, label)
    result: dict[str, dict[str, str]] = {}
    for index, contract in enumerate(contracts):
        contract_id = _text(
            contract.get("contract_id"),
            f"{label}[{index}] contract ID",
        )
        if contract_id in result:
            raise ReleaseBoundaryError(
                f"{label} carries one definition per contract ID"
            )
        result[contract_id] = {
            "version": _text(
                contract.get("version"),
                f"{label}[{index}] version",
            ),
            "digest": _text(
                contract.get("digest"),
                f"{label}[{index}] digest",
            ),
        }
    return result


def _text(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ReleaseBoundaryError(f"{label} carries one non-empty value")
    return value


def _equal(actual: Any, expected: Any, label: str) -> None:
    if actual != expected:
        raise ReleaseBoundaryError(
            f"{label} matches the executable selected-future contract"
        )
