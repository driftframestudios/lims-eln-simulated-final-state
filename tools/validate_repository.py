from __future__ import annotations

import json
from hashlib import sha256
from pathlib import Path
import sys
import tempfile


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from lims_eln_sim.cli import load_json
from lims_eln_sim.artifact_boundary import verify_reproducible_artifacts
from lims_eln_sim.contract_v1 import (
    canonical_digest as contract_digest,
    contract_reference,
)
from lims_eln_sim.database_oracle import validate_database_oracle
from lims_eln_sim.domain import digest
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
    manifest = load_json(ROOT / "release/repository-role.json")
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
    shared_contract_binding = manifest["external_contract_bindings"][
        "shared_contract_nucleus"
    ]
    released_contract_reference = contract_reference()
    expected_contract_digests = {
        field: released_contract_reference[field]
        for field in (
            "golden_scenario_document_digest",
            "golden_scenario_validated_model_digest",
            "observation_schema_document_digest",
            "golden_result_projection_schema_document_digest",
        )
    }
    observed_contract_digests = {
        field: shared_contract_binding.get(field)
        for field in expected_contract_digests
    }
    if observed_contract_digests != expected_contract_digests:
        drift["external_contract_bindings.shared_contract_nucleus"] = {
            "manifest": observed_contract_digests,
            "derived": expected_contract_digests,
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
