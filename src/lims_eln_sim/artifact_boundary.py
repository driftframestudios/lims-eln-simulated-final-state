"""Deterministic boundary checks for generated simulation artifacts."""

from __future__ import annotations

from hashlib import sha256
import os
from pathlib import Path
import stat

from .contract_v1 import canonical_digest, strict_json_loads
from .domain import digest


SIMULATION_ARTIFACTS = frozenset(
    {
        "acceptance-drafts.json",
        "bounded-caller.json",
        "future-reality-closure-bundle.json",
        "migration-report.json",
        "observation-envelope.json",
        "receipt-closure-summary.json",
        "restore-report.json",
        "result.json",
        "scenario-execution.json",
        "security-exercise.json",
        "simulated-receipt-closure.json",
        "simulated-receipts.json",
        "telemetry-summary.json",
    }
)


class ArtifactBoundaryError(ValueError):
    """Generated artifacts return to a reproducible JSON output path."""


def artifact_inventory(root: Path) -> dict[str, str]:
    """Return byte identities for one regular-file, strict-JSON artifact tree."""

    if root.is_symlink() or not root.is_dir():
        raise ArtifactBoundaryError(
            "artifact root requires one concrete output directory"
        )
    inventory: dict[str, str] = {}
    documents: dict[str, object] = {}
    for path in sorted(root.rglob("*")):
        relative = path.relative_to(root).as_posix()
        if path.is_symlink():
            raise ArtifactBoundaryError(
                f"artifact {relative} requires a regular output file"
            )
        if path.is_dir():
            continue
        content = _read_regular_file(path, relative)
        if path.suffix != ".json":
            raise ArtifactBoundaryError(
                f"artifact {relative} requires the released JSON output format"
            )
        try:
            documents[relative] = strict_json_loads(content)
        except ValueError as error:
            raise ArtifactBoundaryError(
                f"artifact {relative} requires strict JSON: {error}"
            ) from error
        inventory[relative] = "sha256:" + sha256(content).hexdigest()
    observed = set(inventory)
    missing = sorted(SIMULATION_ARTIFACTS - observed)
    unexpected = sorted(observed - SIMULATION_ARTIFACTS)
    if missing or unexpected:
        details = []
        if missing:
            details.append("missing: " + ", ".join(missing))
        if unexpected:
            details.append("unexpected: " + ", ".join(unexpected))
        raise ArtifactBoundaryError(
            "simulation output requires the released artifact family; "
            + "; ".join(details)
        )
    _validate_document_links(documents)
    return inventory


def verify_reproducible_artifacts(first: Path, replay: Path) -> dict[str, str]:
    """Prove two isolated outputs carry the same paths and exact bytes."""

    first_inventory = artifact_inventory(first)
    replay_inventory = artifact_inventory(replay)
    first_paths = set(first_inventory)
    replay_paths = set(replay_inventory)
    missing = sorted(first_paths - replay_paths)
    unexpected = sorted(replay_paths - first_paths)
    changed = sorted(
        path
        for path in first_paths & replay_paths
        if first_inventory[path] != replay_inventory[path]
    )
    if missing or unexpected or changed:
        details = []
        if missing:
            details.append("missing on replay: " + ", ".join(missing))
        if unexpected:
            details.append("new on replay: " + ", ".join(unexpected))
        if changed:
            details.append("byte drift: " + ", ".join(changed))
        raise ArtifactBoundaryError(
            "isolated simulation replay requires the same artifact identities; "
            + "; ".join(details)
        )
    return first_inventory


def _read_regular_file(path: Path, relative: str) -> bytes:
    flags = os.O_RDONLY
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    try:
        descriptor = os.open(path, flags)
    except OSError as error:
        raise ArtifactBoundaryError(
            f"artifact {relative} requires a readable regular file"
        ) from error
    with os.fdopen(descriptor, "rb") as stream:
        if not stat.S_ISREG(os.fstat(stream.fileno()).st_mode):
            raise ArtifactBoundaryError(
                f"artifact {relative} requires a regular output file"
            )
        return stream.read()


def _validate_document_links(documents: dict[str, object]) -> None:
    result = documents["result.json"]
    if not isinstance(result, dict):
        raise ArtifactBoundaryError("result.json requires one simulation object")
    linked_documents = {
        "observation-envelope.json": result.get("observation"),
        "scenario-execution.json": result.get("scenario_execution"),
        "migration-report.json": _nested(result, "result", "migration"),
        "restore-report.json": _nested(result, "result", "restore"),
        "security-exercise.json": _nested(
            result,
            "result",
            "security_exercise",
        ),
        "bounded-caller.json": _nested(result, "result", "bounded_caller"),
        "telemetry-summary.json": _nested(result, "result", "telemetry"),
        "acceptance-drafts.json": result.get("acceptance_drafts"),
        "simulated-receipts.json": result.get("receipts"),
        "simulated-receipt-closure.json": result.get("governance_closure"),
        "receipt-closure-summary.json": result.get("receipt_closure_summary"),
    }
    drift = sorted(
        name
        for name, expected in linked_documents.items()
        if documents[name] != expected
    )
    if drift:
        raise ArtifactBoundaryError(
            "generated documents require the projections carried by result.json; "
            "drift: "
            + ", ".join(drift)
        )

    observation = documents["observation-envelope.json"]
    scenario_execution = documents["scenario-execution.json"]
    core = result.get("result")
    if result.get("observation_digest") != canonical_digest(observation):
        raise ArtifactBoundaryError(
            "observation-envelope.json requires the digest carried by result.json"
        )
    if result.get("scenario_execution_digest") != canonical_digest(
        scenario_execution
    ):
        raise ArtifactBoundaryError(
            "scenario-execution.json requires the digest carried by result.json"
        )
    if result.get("content_digest") != digest(core):
        raise ArtifactBoundaryError(
            "result.json requires the digest of its complete result projection"
        )

    closure = documents["future-reality-closure-bundle.json"]
    if not isinstance(closure, dict):
        raise ArtifactBoundaryError(
            "future-reality-closure-bundle.json requires one closure object"
        )
    closure_links = {
        "future_reality_version": result.get("future_reality_version"),
        "governance_closure_digest": digest(result.get("governance_closure")),
        "governance_closure": result.get("governance_closure"),
        "detailed_receipts": result.get("receipts"),
        "source_result_digest": result.get("content_digest"),
    }
    if closure.get("bundle_version") != "2.0.1" or any(
        closure.get(key) != value for key, value in closure_links.items()
    ):
        raise ArtifactBoundaryError(
            "future-reality-closure-bundle.json requires the selected-future "
            "coordinates carried by result.json"
        )


def _nested(value: dict, *path: str) -> object:
    current: object = value
    for field in path:
        if not isinstance(current, dict):
            return None
        current = current.get(field)
    return current
