#!/usr/bin/env python3
"""Validate accepted sibling coordinates and their current receiving horizon."""

from __future__ import annotations

import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from lims_eln_sim.cli import load_json


EXPECTED_IMPLEMENTATION_COORDINATE = {
    "release": "v0.3.2",
    "tag_object_oid": "c3db01079b88622f06e8714c8bcbdf0dc1803a10",
    "commit": "fe0bd2a08ac1697ce18ca583d9631faae7db7132",
    "digest": "git-tree-sha1:eb8eadb27a9e07c6069a1946f115a0083d94af5c",
    "archive_digest": (
        "sha256:0ea3db3099e3485f65d238fb2e194c6bfd9b9a90f6642431c4a96974ebcc3c16"
    ),
    "observation_carrier_commit": "b3fcf07445bc0c049daa00b03d6fe583962085cf",
    "coordinate_status": "release_observed",
    "source_binding_status": "accepted_program_coordinate",
}


def expected_comparison_coordinate(canonical_closure_digest: str) -> dict:
    """Return the exact accepted Comparison 0.3.2 coordinate family."""
    return {
        "release": "comparison-v0.3.2",
        "tag_object_oid": "ccc4b206d9071933516863ee0eb3f5b091fc76b0",
        "commit": "0289ff835c790693a769347e69da0abdcfaa47de",
        "digest": "git-tree-sha1:60c85e4206e2d487dac83d521401816dec0f34ae",
        "archive_digest": (
            "sha256:5c1697f98655ce1979fcc6f4a85b719e0c44afde8a3004037d19dd1416d0720e"
        ),
        "observation_carrier": {
            "commit": "2cca88982444ebc8280f9eb2891d97bf25dbeb95",
            "receipt_path": "receipts/promotion-observation-v0.3.2.json",
            "receipt_file_sha256": (
                "sha256:acccb507f0675cdc079aa56bc12299bd4ce533344cb150e42dba1c991"
                "c024fd4"
            ),
        },
        "coordinate_status": "release_observed",
        "canonical_closure_digest": canonical_closure_digest,
        "receipt_schema": "2.0.1",
        "golden_specimen_report": {
            "report_digest": (
                "sha256:a2f92ae4acb9fb7d835d0a9b126bb1932ae69b06b094303180dd9fea"
                "7217b77c"
            ),
            "leaf_paths_compared": 17,
            "classification_counts": {
                "agreement": 10,
                "explainable_variation": 4,
                "material_divergence": 3,
            },
            "material_divergence_paths": [
                "$.measurement.analyte",
                "$.measurement.value",
                "$.measurement.unit",
            ],
            "material_divergence_receiver": "accountable_scientific_mapping",
        },
        "publication": {
            "coordinate_status": "published",
            "record_carrier_commit": "c854a6f58c587a0b099efa24d2b745b2bd7187df",
            "source_revision": "2cca88982444ebc8280f9eb2891d97bf25dbeb95",
            "docs_revision": "6ccc087875b439eb70304771f534434acae3f01c",
            "projection_manifest_path": "projection-manifest.json",
            "projection_manifest_sha256": (
                "sha256:38d01a78be6804d04bc4f24c412777b8cb08fe2c65372e278480c106"
                "b4bcbeea"
            ),
            "canonical_origin": "https://cometspectrum.io/",
        },
    }


EXPECTED_HORIZON_STATE = {
    "current_item_ids": ["HORIZON-ACCOUNTABLE-SCIENTIFIC-MAPPING"],
    "work_item_states": {
        "HORIZON-COMPARATIVE-ADMISSION": "complete",
        "HORIZON-ACCOUNTABLE-SCIENTIFIC-MAPPING": "ready",
        "HORIZON-SIMULATION-EXTENSIONS": "waiting",
    },
    "mapping_owner_role": "accountable scientific mapping",
    "mapping_dependency_ids": ["HORIZON-COMPARATIVE-ADMISSION"],
}


def validate_living_constellation(
    constellation: dict,
    horizon: dict,
    first_receipt: dict,
    canonical_closure_digest: str,
) -> list[str]:
    """Return material differences from the accepted living coordinates."""
    findings: list[str] = []
    if constellation.get("constellation_version") != "0.3.2":
        findings.append("constellation version differs from accepted version 0.3.2")
    if constellation.get("implementation") != EXPECTED_IMPLEMENTATION_COORDINATE:
        findings.append("Implementation coordinate differs from accepted v0.3.2")
    if constellation.get("comparison") != expected_comparison_coordinate(
        canonical_closure_digest
    ):
        findings.append(
            "Comparison coordinate family differs from accepted comparison-v0.3.2"
        )
    if (
        constellation.get("simulation", {}).get("canonical_closure_digest")
        != canonical_closure_digest
    ):
        findings.append(
            "Simulation coordinate differs from the retained canonical closure"
        )

    work_items = {
        item.get("item_id"): item
        for item in horizon.get("work_items", [])
        if isinstance(item, dict) and item.get("item_id")
    }
    observed_states = {
        item_id: work_items.get(item_id, {}).get("state")
        for item_id in EXPECTED_HORIZON_STATE["work_item_states"]
    }
    if horizon.get("current_item_ids") != EXPECTED_HORIZON_STATE[
        "current_item_ids"
    ]:
        findings.append(
            "Coordination Horizon current receiver differs from accountable "
            "scientific mapping"
        )
    if observed_states != EXPECTED_HORIZON_STATE["work_item_states"]:
        findings.append(
            "Coordination Horizon states differ from the accepted Comparison return"
        )
    mapping = work_items.get("HORIZON-ACCOUNTABLE-SCIENTIFIC-MAPPING", {})
    if mapping.get("owner_role") != EXPECTED_HORIZON_STATE["mapping_owner_role"]:
        findings.append(
            "scientific mapping work item differs from its accountable owner"
        )
    if mapping.get("dependency_ids") != EXPECTED_HORIZON_STATE[
        "mapping_dependency_ids"
    ]:
        findings.append(
            "scientific mapping work item differs from its Comparison dependency"
        )

    horizon_id = horizon.get("horizon_id")
    if first_receipt.get("coordination_horizon_id") != horizon_id:
        findings.append("First Receipt differs from the current Coordination Horizon")
    current_timestamp = horizon.get("as_of")
    observed_timestamps = {
        current_timestamp,
        horizon.get("metadata", {}).get("updated_at"),
        first_receipt.get("as_of"),
        first_receipt.get("metadata", {}).get("updated_at"),
    }
    if len(observed_timestamps) != 1 or current_timestamp is None:
        findings.append(
            "living orientation timestamps do not describe one current state"
        )

    summary = first_receipt.get("current_horizon_summary", "")
    if not all(
        marker in summary
        for marker in (
            "Enterprise v0.3.2",
            "comparison-v0.3.2",
            "accountable scientific mapping",
        )
    ):
        findings.append("First Receipt summary differs from the accepted current route")

    handoff = first_receipt.get("handoff", {})
    if handoff.get("recipient_role") != "accountable scientific mapping":
        findings.append("First Receipt handoff differs from the current receiver")
    if handoff.get("action_ids") != EXPECTED_HORIZON_STATE["current_item_ids"]:
        findings.append("First Receipt handoff differs from the current action")
    next_safe_action = handoff.get("next_safe_action", "")
    if not all(
        marker in next_safe_action
        for marker in ("analyte", "value", "unit", "owning source")
    ):
        findings.append(
            "First Receipt handoff differs from the material mapping action"
        )
    success_evidence = handoff.get("success_evidence", "")
    if not all(
        marker in success_evidence
        for marker in (
            "selected-future baseline",
            "separate observed-evidence route",
        )
    ):
        findings.append(
            "First Receipt success evidence differs from the evidence boundary"
        )

    source_permissions = {
        item.get("source"): item
        for item in first_receipt.get("source_permissions", [])
        if isinstance(item, dict) and item.get("source")
    }
    coordinate_sources = (
        "accepted Enterprise v0.3.2 release and observation",
        "accepted Comparison v0.3.2 release, observation, and publication",
    )
    for source in coordinate_sources:
        permission = source_permissions.get(source, {})
        if permission.get("permission") != "read" or "constellation.lock.json" not in (
            permission.get("verification", "")
        ):
            findings.append(
                f"First Receipt source permission does not resolve {source} through "
                "the living lock"
            )

    comparison = work_items.get("HORIZON-COMPARATIVE-ADMISSION", {})
    comparison_evidence = [
        *comparison.get("entry_evidence", []),
        *comparison.get("completion_evidence", []),
    ]
    if not any("constellation.lock.json" in item for item in comparison_evidence):
        findings.append(
            "Coordination Horizon does not resolve Comparison through the living lock"
        )
    return findings


def main() -> int:
    constellation = load_json(ROOT / "constellation.lock.json")
    horizon = load_json(ROOT / "COORDINATION-HORIZON.json")
    first_receipt = load_json(ROOT / "first-receipt.json")
    release_role = load_json(ROOT / "release/repository-role.json")
    findings = validate_living_constellation(
        constellation,
        horizon,
        first_receipt,
        release_role["reference_closure_digest"],
    )
    if findings:
        print("Living constellation differs from accepted sibling coordinates:")
        for finding in findings:
            print(f"  - {finding}")
        return 1
    print(
        json.dumps(
            {
                "status": "passed",
                "constellation_version": constellation["constellation_version"],
                "current_item_ids": horizon["current_item_ids"],
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
