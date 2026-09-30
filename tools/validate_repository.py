from __future__ import annotations

import json
from hashlib import sha256
from pathlib import Path
import re
import sys
import tempfile


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

PUBLIC_POSSIBLE_SKILL_METADATA = {
    ".agents/skills/constellation-coherence-reconciliation/SKILL.md": {
        "name": "constellation-coherence-reconciliation",
        "source_band": "public_possible",
        "skill_version": "0.1.0",
        "upstream_repository": (
            "driftframestudios/lims-eln-program-specification"
        ),
        "upstream_path": (
            ".agents/skills/constellation-coherence-reconciliation/SKILL.md"
        ),
        "upstream_revision": "05357fbed16a5b5aca80c239e4c7535f67d5654b",
        "upstream_blob_sha1": "1812603158395e970b5f8d5d7b977513a95e8d82",
        "upstream_sha256": (
            "0c432287d4c5030ad34e7f05dd77aa9ee86c7d3b882ef3388ff2ca9471c2b912"
        ),
        "adaptation_relation": "repository_local_derivative",
    },
    ".agents/skills/contextual-jargon-scan/SKILL.md": {
        "name": "contextual-jargon-scan",
        "source_band": "public_possible",
        "skill_version": "0.1.0",
        "upstream_repository": "driftframestudios/human-ai-systems-exemplars",
        "upstream_path": ".agents/skills/contextual-jargon-scan/SKILL.md",
        "upstream_revision": "0c023343e46cd9b1333a63c2d509787352fbad14",
        "upstream_blob_sha1": "3c3a94db99152385253e0281c8afa8fea8208ac5",
        "upstream_sha256": (
            "da383f99eaff364d7e17c3bff93d8da618ec95894a45ff78a9620d8d7fc81523"
        ),
        "adaptation_relation": "repository_local_derivative",
    },
    ".agents/skills/repository-reentry/SKILL.md": {
        "name": "repository-reentry",
        "source_band": "public_possible",
        "skill_version": "0.1.0",
        "upstream_repository": "driftframestudios/human-ai-systems-exemplars",
        "upstream_path": ".agents/skills/repository-reentry/SKILL.md",
        "upstream_revision": "0c023343e46cd9b1333a63c2d509787352fbad14",
        "upstream_blob_sha1": "ac2c3732826c515b236598af10e0a204dbe14ace",
        "upstream_sha256": (
            "c60bb1bac3a993c78d94b1d05aaa7a97761b99275fc9acdc8285acba6f688f02"
        ),
        "adaptation_relation": "repository_local_derivative",
    },
    ".agents/skills/source-authority-mapping/SKILL.md": {
        "name": "source-authority-mapping",
        "source_band": "public_possible",
        "skill_version": "0.1.0",
        "upstream_repository": "driftframestudios/human-ai-systems-exemplars",
        "upstream_path": ".agents/skills/source-authority-mapping/SKILL.md",
        "upstream_revision": "0c023343e46cd9b1333a63c2d509787352fbad14",
        "upstream_blob_sha1": "112830e9b70540b0bc9a8535ab77c7a04c1a5926",
        "upstream_sha256": (
            "1420eaee7f6d58805c29eaff23644d4982fdf1f12d2f6ce3cc39c65791939aff"
        ),
        "adaptation_relation": "repository_local_derivative",
    },
}

_SKILL_REQUIRED_SECTIONS = (
    "## Contract",
    "## Operating sequence",
    "## Completion",
)
_GIT_OID = re.compile(r"[0-9a-f]{40}")
_SHA256 = re.compile(r"[0-9a-f]{64}")

from lims_eln_sim.cli import load_json
from lims_eln_sim.artifact_boundary import verify_reproducible_artifacts
from lims_eln_sim.contract_v1 import (
    canonical_digest as contract_digest,
    contract_reference,
)
from lims_eln_sim.database_oracle import validate_database_oracle
from lims_eln_sim.domain import digest
from lims_eln_sim.promotion_receipt import (
    SCHEMA_VERSION as PROMOTION_SCHEMA_VERSION,
    canonical_digest as promotion_digest,
    file_digest,
    validate_promotion_receipt,
)
from lims_eln_sim.release_boundary import validate_release_alignment
from lims_eln_sim.safety import synthetic_redaction_key
from lims_eln_sim.simulation import (
    FORECAST_METADATA,
    closure_bundle,
    run,
    write_bundle,
)
from check_artifacts import PATTERNS
from check_bounded_automation import validate_repository_automation
from check_living_constellation import validate_living_constellation


def parse_skill_source(path: Path) -> tuple[dict[str, str], str]:
    """Return the simple scalar front matter and complete skill source."""
    content = path.read_text(encoding="utf-8")
    lines = content.splitlines()
    if not lines or lines[0] != "---":
        raise ValueError(f"{path} requires YAML front matter")
    try:
        closing = lines.index("---", 1)
    except ValueError as error:
        raise ValueError(f"{path} has unclosed YAML front matter") from error
    metadata: dict[str, str] = {}
    for line in lines[1:closing]:
        if not line.strip():
            continue
        if ":" not in line:
            raise ValueError(f"{path} has unsupported front-matter line {line!r}")
        key, value = line.split(":", 1)
        metadata[key.strip()] = value.strip().strip('"')
    return metadata, content


def validate_collaboration_workbench(root: Path = ROOT) -> list[str]:
    """Validate the exact copy-local skill workbench and orientation routes."""
    findings: list[str] = []
    skills_root = root / ".agents" / "skills"
    actual_paths = {
        str(path.relative_to(root))
        for path in skills_root.glob("*/SKILL.md")
    }
    expected_paths = set(PUBLIC_POSSIBLE_SKILL_METADATA)
    if actual_paths != expected_paths:
        findings.append(
            "public-possible skill inventory differs: expected "
            f"{sorted(expected_paths)!r}; received {sorted(actual_paths)!r}"
        )
    for relative_path, expected in PUBLIC_POSSIBLE_SKILL_METADATA.items():
        path = root / relative_path
        if not path.is_file():
            continue
        try:
            metadata, content = parse_skill_source(path)
        except ValueError as error:
            findings.append(str(error))
            continue
        observed = {key: metadata.get(key) for key in expected}
        if observed != expected:
            findings.append(
                f"{relative_path} metadata differs: expected {expected!r}; "
                f"received {observed!r}"
            )
        if path.parent.name != metadata.get("name"):
            findings.append(
                f"{relative_path} directory and skill name must match"
            )
        if not _GIT_OID.fullmatch(metadata.get("upstream_revision", "")):
            findings.append(f"{relative_path} requires a full upstream revision")
        if not _GIT_OID.fullmatch(metadata.get("upstream_blob_sha1", "")):
            findings.append(f"{relative_path} requires an upstream blob identity")
        if not _SHA256.fullmatch(metadata.get("upstream_sha256", "")):
            findings.append(f"{relative_path} requires an upstream SHA-256 identity")
        for heading in _SKILL_REQUIRED_SECTIONS:
            if heading not in content:
                findings.append(f"{relative_path} requires {heading}")
        if "notion.so" in content or "app.notion.com" in content:
            findings.append(
                f"{relative_path} must remain usable through repository-local "
                "guidance; private workspace locator found"
            )
    catalog_path = skills_root / "README.md"
    if not catalog_path.is_file():
        findings.append(".agents/skills/README.md is required for skill selection")
    else:
        catalog = catalog_path.read_text(encoding="utf-8")
        for relative_path in expected_paths:
            skill_name = Path(relative_path).parent.name
            if f"({skill_name}/SKILL.md)" not in catalog:
                findings.append(
                    ".agents/skills/README.md must link the local skill route "
                    f"{skill_name}/SKILL.md"
                )
    for orientation_name in ("README.md", "AGENTS.md"):
        orientation_path = root / orientation_name
        if not orientation_path.is_file():
            findings.append(f"{orientation_name} is required for workbench routing")
            continue
        orientation = orientation_path.read_text(encoding="utf-8")
        if ".agents/skills/README.md" not in orientation:
            findings.append(
                f"{orientation_name} must link .agents/skills/README.md"
            )
        for relative_path in expected_paths:
            if relative_path not in orientation:
                findings.append(
                    f"{orientation_name} must link the exact skill path {relative_path}"
                )
    return findings


def validate_living_constellation_coherence(root: Path = ROOT) -> list[str]:
    """Check material relations among the lock and living re-entry carriers."""
    findings: list[str] = []
    constellation = json.loads(
        (root / "constellation.lock.json").read_text(encoding="utf-8")
    )
    horizon = json.loads(
        (root / "COORDINATION-HORIZON.json").read_text(encoding="utf-8")
    )
    first_receipt = json.loads(
        (root / "first-receipt.json").read_text(encoding="utf-8")
    )
    simulation = constellation.get("simulation", {})
    comparison = constellation.get("comparison", {})
    if simulation.get("canonical_closure_digest") != comparison.get(
        "canonical_closure_digest"
    ):
        findings.append(
            "Simulation and Comparison canonical closure relations differ"
        )
    for role, coordinate in (("Simulation", simulation), ("Comparison", comparison)):
        if coordinate.get("coordinate_status") != "release_observed":
            findings.append(f"{role} coordinate must be release_observed")
        for field in ("tag_object_oid", "commit", "digest", "archive_digest"):
            if not coordinate.get(field):
                findings.append(f"{role} coordinate is missing {field}")
    work_items = {
        item["item_id"]: item for item in horizon.get("work_items", [])
    }
    comparison_item = work_items.get("HORIZON-COMPARATIVE-ADMISSION", {})
    if comparison_item.get("state") != "complete":
        findings.append("accepted Comparison admission must remain complete")

    current_item_ids = horizon.get("current_item_ids")
    if (
        not isinstance(current_item_ids, list)
        or not current_item_ids
        or not all(isinstance(item, str) and item for item in current_item_ids)
        or len(current_item_ids) != len(set(current_item_ids))
    ):
        findings.append("current horizon must name distinct actionable work items")
        current_item_ids = []
    current_items = [work_items.get(item_id) for item_id in current_item_ids]
    if any(item is None for item in current_items):
        findings.append("current horizon items must resolve to declared work items")
    elif any(item.get("state") not in {"ready", "active"} for item in current_items):
        findings.append("current horizon items must carry ready or active state")

    if first_receipt.get("coordination_horizon_id") != horizon.get("horizon_id"):
        findings.append("First Receipt must resolve the current Coordination Horizon")
    handoff = first_receipt.get("handoff", {})
    if handoff.get("action_ids") != current_item_ids:
        findings.append("First Receipt actions must match the current horizon items")
    current_owner_roles = {
        item.get("owner_role") for item in current_items if item is not None
    }
    if (
        len(current_owner_roles) != 1
        or handoff.get("recipient_role") not in current_owner_roles
    ):
        findings.append("First Receipt recipient must own the current horizon items")
    if not first_receipt.get("current_horizon_summary", "").strip():
        findings.append(
            "First Receipt must provide a current horizon summary"
        )
    return findings


def _repository_json_documents() -> int:
    count = 0
    for path in sorted(ROOT.rglob("*.json")):
        if any(part in {".git", "build", "__pycache__"} for part in path.parts):
            continue
        load_json(path)
        count += 1
    return count


def _repository_secret_shape_findings() -> list[str]:
    findings: list[str] = []
    for path in sorted(ROOT.rglob("*")):
        if (
            not path.is_file()
            or any(part in {".git", "build", "__pycache__"} for part in path.parts)
            or path.suffix in {".pyc", ".png", ".jpg", ".jpeg", ".gif", ".pdf"}
        ):
            continue
        try:
            content = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        if any(pattern.search(content) for pattern in PATTERNS):
            findings.append(str(path.relative_to(ROOT)))
    return findings


def main() -> int:
    workbench_findings = validate_collaboration_workbench()
    if workbench_findings:
        raise ValueError(
            "collaboration workbench differs from its local contract: "
            + "; ".join(workbench_findings)
        )
    coherence_findings = validate_living_constellation_coherence()
    if coherence_findings:
        raise ValueError(
            "living constellation differs from its accepted coordination state: "
            + "; ".join(coherence_findings)
        )
    manifest = load_json(ROOT / "release/repository-role.json")
    promotion_binding = manifest["promotion_receipt_contract"]
    promotion_schema_path = ROOT / promotion_binding["schema_path"]
    promotion_receipt_path = ROOT / promotion_binding["receipt_path"]
    promotion_schema = load_json(promotion_schema_path)
    promotion_receipt = load_json(promotion_receipt_path)
    validate_promotion_receipt(promotion_receipt)
    expected_promotion_binding = {
        "schema_path": "schemas/promotion-receipt.schema.json",
        "schema_version": PROMOTION_SCHEMA_VERSION,
        "schema_file_sha256": file_digest(promotion_schema_path),
        "receipt_path": "receipts/promotion-receipt.json",
        "receipt_canonical_json_digest": promotion_digest(promotion_receipt),
    }
    if promotion_binding != expected_promotion_binding:
        raise ValueError(
            "promotion receipt contract differs from its source carriers: "
            + json.dumps(
                {
                    "manifest": promotion_binding,
                    "derived": expected_promotion_binding,
                },
                sort_keys=True,
            )
        )
    if promotion_schema.get("$id") != (
        "https://schemas.driftframe.org/lims-eln-simulated-final-state/"
        "v1.0.0/promotion-receipt.schema.json"
    ):
        raise ValueError(
            "promotion receipt schema keeps its exact repository-owned identity"
        )
    if promotion_receipt["promotion_state"] != "release_observed":
        raise ValueError(
            "release 0.3.1 carries its observed signed promotion coordinate"
        )
    release_subject = promotion_receipt["release_subject"]
    expected_hosted_contexts = [
        {
            "name": "Repository validation",
            "run_id": "33588934525",
            "conclusion": "success",
        },
        {
            "name": "branch-shape",
            "run_id": "33588934514",
            "conclusion": "success",
        },
    ]
    if release_subject["hosted_check_contexts"] != expected_hosted_contexts:
        raise ValueError(
            "promotion receipt names the two accepted PR #26 hosted checks"
        )
    expected_release_coordinates = {
        "seed_governance_commit": "716d4581d723a5c1b56f16efdbcd25790549ae33",
        "seed_program_specification_commit": (
            "fc7707134b58ed12ad349bf649d2af1c3689bd01"
        ),
        "coordinate_status": "release_observed",
        "reviewed_candidate_commit": (
            "91bfdba0fd4bc78a0d5d5e25f192ad0d18774bcf"
        ),
        "reviewed_candidate_tree_digest": (
            "git-tree-sha1:595ae59f25f522732577c5f8e00709f023464a6d"
        ),
        "accepted_commit": release_subject["commit_oid"],
        "accepted_tree_digest": "git-tree-sha1:" + release_subject["tree_oid"],
        "tag_object_oid": release_subject["tag_object_oid"],
        "archive_digest": release_subject["archive_digest"],
        "promotion_receipt_id": promotion_receipt["promotion_receipt_id"],
    }
    if manifest["release_coordinates"] != expected_release_coordinates:
        raise ValueError(
            "release coordinates differ from the observed promotion receipt "
            "and reviewed candidate"
        )
    automation_findings = validate_repository_automation(
        ROOT, manifest["automation_controls"]
    )
    if automation_findings:
        raise ValueError(
            "bounded hosted automation differs from its source contract: "
            + "; ".join(automation_findings)
        )
    json_count = _repository_json_documents()
    fixture = load_json(ROOT / "fixtures/golden-specimen.json")
    database_oracle = load_json(
        ROOT / "database/final-state-database-oracle-v1.json"
    )

    def reference_run() -> dict:
        return run(
            load_json(ROOT / "fixtures/golden-specimen.json"),
            intended_use_profile=load_json(
                ROOT
                / "specification/intended-use-and-applicability-profile.json"
            ),
            migration_corpus=load_json(
                ROOT / "fixtures/representative-migration-corpus.json"
            ),
            database_oracle=database_oracle,
            redaction_key=synthetic_redaction_key(fixture["redaction_key_id"]),
        )

    result = reference_run()
    replay = reference_run()
    with (
        tempfile.TemporaryDirectory(prefix="simulation-first-") as first_directory,
        tempfile.TemporaryDirectory(prefix="simulation-replay-") as replay_directory,
    ):
        first_path = Path(first_directory)
        replay_path = Path(replay_directory)
        write_bundle(result, first_path)
        write_bundle(replay, replay_path)
        artifact_inventory = verify_reproducible_artifacts(
            first_path,
            replay_path,
        )
    retained = load_json(
        ROOT / "release/future-reality-2028-06-30-v1.json"
    )
    generated = closure_bundle(result)
    if retained != generated:
        raise ValueError(
            "retained selected-future closure differs from regenerated evidence"
        )
    first_receipt = load_json(ROOT / "first-receipt.json")
    machine_node = load_json(ROOT / "machine-node.json")
    horizon = load_json(ROOT / "COORDINATION-HORIZON.json")
    assumptions_ledger = load_json(ROOT / "ledgers/assumptions.json")
    validate_release_alignment(
        forecast_metadata=FORECAST_METADATA,
        governance_closure=result["governance_closure"],
        detailed_receipts=result["receipts"],
        bounded_caller=result["result"]["bounded_caller"],
        assumptions_ledger=assumptions_ledger,
        release_manifest=manifest,
        first_receipt=first_receipt,
        machine_node=machine_node,
        coordination_horizon=horizon,
    )
    database_coordinates = validate_database_oracle(database_oracle)
    expected = {
        "reference_result_digest": result["content_digest"],
        "reference_simulation_observation_digest": result[
            "observation_digest"
        ],
        "reference_scenario_execution_digest": result[
            "scenario_execution_digest"
        ],
        "reference_closure_digest": digest(result["governance_closure"]),
        "aggregate_closure_artifact_digest": retained["governance_closure"][
            "aggregate_artifacts"
        ][0]["digest"],
    }
    drift = {
        field: {"manifest": manifest.get(field), "derived": value}
        for field, value in expected.items()
        if manifest.get(field) != value
    }
    canonical = manifest["canonical_closure_bundle"]
    if canonical.get("canonical_json_digest") != digest(retained):
        drift["canonical_closure_bundle.canonical_json_digest"] = {
            "manifest": canonical.get("canonical_json_digest"),
            "derived": digest(retained),
        }
    retained_path = ROOT / canonical["path"]
    file_sha256 = f"sha256:{sha256(retained_path.read_bytes()).hexdigest()}"
    if canonical.get("file_sha256") != file_sha256:
        drift["canonical_closure_bundle.file_sha256"] = {
            "manifest": canonical.get("file_sha256"),
            "derived": file_sha256,
        }
    oracle_binding = manifest["database_oracle"]
    expected_oracle_binding = {
        "path": "database/final-state-database-oracle-v1.json",
        "bundle_version": database_oracle["oracle_version"],
        "canonical_json_digest": contract_digest(database_oracle),
        "release_coordinates": database_coordinates.as_dict(),
    }
    if oracle_binding != expected_oracle_binding:
        drift["database_oracle"] = {
            "manifest": oracle_binding,
            "derived": expected_oracle_binding,
        }
    observation_oracle_binding = result["observation"]["result"][
        "producer_detail"
    ]["database_oracle"]
    expected_observation_oracle_binding = {
        "oracle_id": database_oracle["oracle_id"],
        "oracle_version": database_oracle["oracle_version"],
        "canonical_json_digest": contract_digest(database_oracle),
        "release_coordinates": database_coordinates.as_dict(),
    }
    if observation_oracle_binding != expected_observation_oracle_binding:
        drift["observation.result.producer_detail.database_oracle"] = {
            "emitted": observation_oracle_binding,
            "derived": expected_observation_oracle_binding,
        }
    released_contract_reference = contract_reference()
    expected_shared_contract_binding = {
        "contract_id": "LIMS-ELN-CONTRACT-NUCLEUS",
        "version": released_contract_reference["contract_version"],
        "authority": "driftframestudios/lims-eln-program-specification",
        "distribution": released_contract_reference["distribution_requirement"],
        "distribution_state": released_contract_reference["distribution_state"],
        "source_commit": released_contract_reference["source_commit"],
        "source_tree": released_contract_reference["source_tree"],
        "source_identity_digest": released_contract_reference[
            "source_identity_digest"
        ],
        "acceptance_lineage_commit": released_contract_reference[
            "acceptance_lineage_commit"
        ],
        "binding_path": (
            "src/lims_eln_sim/contract_resources/contract-binding.v1.json"
        ),
        "golden_scenario_document_digest": released_contract_reference[
            "golden_scenario_document_digest"
        ],
        "golden_scenario_validated_model_digest": released_contract_reference[
            "golden_scenario_validated_model_digest"
        ],
        "observation_schema_document_digest": released_contract_reference[
            "observation_schema_document_digest"
        ],
        "golden_result_projection_schema_document_digest": (
            released_contract_reference[
                "golden_result_projection_schema_document_digest"
            ]
        ),
    }
    shared_contract_binding = manifest["external_contract_bindings"][
        "shared_contract_nucleus"
    ]
    if shared_contract_binding != expected_shared_contract_binding:
        drift["external_contract_bindings.shared_contract_nucleus"] = {
            "manifest": shared_contract_binding,
            "derived": expected_shared_contract_binding,
        }
    constellation = load_json(ROOT / "constellation.lock.json")
    expected_specification_coordinate = {
        "release": None,
        "package_version": released_contract_reference["distribution_version"],
        "commit": released_contract_reference["source_commit"],
        "digest": (
            "git-tree-sha1:" + released_contract_reference["source_tree"]
        ),
        "source_identity_digest": released_contract_reference[
            "source_identity_digest"
        ],
        "acceptance_lineage_commit": released_contract_reference[
            "acceptance_lineage_commit"
        ],
        "coordinate_status": "accepted_package_source",
        "complete_specification_release": "pending",
    }
    if constellation.get("specification") != expected_specification_coordinate:
        drift["constellation.specification"] = {
            "manifest": constellation.get("specification"),
            "derived": expected_specification_coordinate,
        }
    living_findings = validate_living_constellation(
        constellation,
        horizon,
        first_receipt,
        digest(result["governance_closure"]),
    )
    if living_findings:
        drift["living_constellation"] = living_findings
    expected_governance_binding = {
        "authority": "driftframestudios/site-reading-governance",
        **constellation["governance"],
    }
    observed_governance_binding = manifest["external_contract_bindings"].get(
        "accepted_governance"
    )
    if observed_governance_binding != expected_governance_binding:
        drift["external_contract_bindings.accepted_governance"] = {
            "manifest": observed_governance_binding,
            "derived": expected_governance_binding,
        }
    expected_contract_bindings = {
        "governance_schema": constellation["governance"]["schema_version"],
        "governance_release": constellation["governance"]["release"],
        "program_contract_package": released_contract_reference[
            "distribution_version"
        ],
    }
    for field, expected_value in expected_contract_bindings.items():
        observed_value = manifest["contract_bindings"].get(field)
        if observed_value != expected_value:
            drift[f"contract_bindings.{field}"] = {
                "manifest": observed_value,
                "derived": expected_value,
            }
    if manifest["contract_bindings"].get(
        "golden_specimen_result_projection_schema"
    ) != "1.0.0":
        drift["contract_bindings.golden_specimen_result_projection_schema"] = {
            "manifest": manifest["contract_bindings"].get(
                "golden_specimen_result_projection_schema"
            ),
            "derived": "1.0.0",
        }
    expected_assumption_ids = {
        item["assumption_id"] for item in assumptions_ledger["assumptions"]
    }
    selected_assumption_ids = set(
        result["governance_closure"]["future_reality"]["assumption_ids"]
    )
    if selected_assumption_ids != expected_assumption_ids:
        drift["selected_future_assumption_ids"] = {
            "ledger": sorted(expected_assumption_ids),
            "selected_future": sorted(selected_assumption_ids),
        }
    expected_assumptions_binding = {
        "path": "ledgers/assumptions.json",
        "canonical_json_digest": digest(assumptions_ledger),
    }
    if manifest.get("assumptions_ledger") != expected_assumptions_binding:
        drift["assumptions_ledger"] = {
            "manifest": manifest.get("assumptions_ledger"),
            "derived": expected_assumptions_binding,
        }
    if drift:
        raise ValueError(
            "release manifest differs from regenerated evidence: "
            + json.dumps(drift, sort_keys=True)
        )
    findings = _repository_secret_shape_findings()
    if findings:
        raise ValueError(
            "repository files require governed credential storage: "
            + ", ".join(findings)
        )
    print(
        json.dumps(
            {
                "status": "passed",
                "collaboration_skills": len(PUBLIC_POSSIBLE_SKILL_METADATA),
                "json_documents": json_count,
                "source_result_digest": result["content_digest"],
                "governance_closure_digest": expected[
                    "reference_closure_digest"
                ],
                "canonical_bundle_digest": digest(retained),
                "database_oracle_digest": digest(database_oracle),
                "database_release": database_coordinates.database_release,
                "assumptions_ledger_digest": digest(assumptions_ledger),
                "artifact_inventory_digest": digest(artifact_inventory),
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
