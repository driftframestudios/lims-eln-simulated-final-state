from __future__ import annotations

import json
from hashlib import sha256
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from lims_eln_sim.cli import load_json
from lims_eln_sim.database_oracle import validate_database_oracle
from lims_eln_sim.domain import digest
from lims_eln_sim.safety import synthetic_redaction_key
from lims_eln_sim.simulation import closure_bundle, run
from check_artifacts import PATTERNS


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
    json_count = _repository_json_documents()
    fixture = load_json(ROOT / "fixtures/golden-specimen.json")
    result = run(
        fixture,
        intended_use_profile=load_json(
            ROOT / "specification/intended-use-and-applicability-profile.json"
        ),
        migration_corpus=load_json(
            ROOT / "fixtures/representative-migration-corpus.json"
        ),
        redaction_key=synthetic_redaction_key(fixture["redaction_key_id"]),
    )
    retained = load_json(
        ROOT / "release/future-reality-2028-06-30-v1.json"
    )
    generated = closure_bundle(result)
    if retained != generated:
        raise ValueError(
            "retained selected-future closure differs from regenerated evidence"
        )
    manifest = load_json(ROOT / "release/repository-role.json")
    database_oracle = load_json(
        ROOT / "database/final-state-database-oracle-v1.json"
    )
    database_coordinates = validate_database_oracle(database_oracle)
    expected = {
        "reference_result_digest": result["content_digest"],
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
        "canonical_json_digest": digest(database_oracle),
        "release_coordinates": database_coordinates.as_dict(),
    }
    if oracle_binding != expected_oracle_binding:
        drift["database_oracle"] = {
            "manifest": oracle_binding,
            "derived": expected_oracle_binding,
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
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
