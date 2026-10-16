"""Deterministic boundary checks for generated simulation artifacts."""

from __future__ import annotations

from hashlib import sha256
import io
import json
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

# Native receiving policy: one bounded forecast family, including JSON whitespace.
MAX_ARTIFACT_BYTES = 4 * 1024 * 1024
MAX_TOTAL_ARTIFACT_BYTES = 32 * 1024 * 1024
MAX_ARTIFACT_JSON_DEPTH = 32


class ArtifactBoundaryError(ValueError):
    """Generated artifacts return to a reproducible JSON output path."""


def artifact_inventory(root: Path) -> dict[str, str]:
    """Return byte identities for one regular-file, strict-JSON artifact tree."""

    if root.is_symlink() or not root.is_dir():
        raise ArtifactBoundaryError(
            "artifact root requires one concrete output directory"
        )
    paths = _artifact_paths(root)
    inventory: dict[str, str] = {}
    documents: dict[str, object] = {}
    remaining = MAX_TOTAL_ARTIFACT_BYTES
    for path in paths:
        relative = path.name
        content = _read_regular_file(
            path, relative, maximum_bytes=min(MAX_ARTIFACT_BYTES, remaining)
        )
        remaining -= len(content)
        try:
            documents[relative] = strict_json_loads(_depth_admitted_text(content))
        except ValueError as error:
            raise ArtifactBoundaryError(
                f"artifact {relative} requires strict JSON: {error}"
            ) from error
        inventory[relative] = "sha256:" + sha256(content).hexdigest()
    _validate_document_links(documents)
    return inventory


def _artifact_paths(root: Path) -> tuple[Path, ...]:
    """Admit the closed root family before opening any artifact or subtree."""
    observed: set[str] = set()
    try:
        with os.scandir(root) as entries:
            for entry in entries:
                if entry.name not in SIMULATION_ARTIFACTS:
                    raise ArtifactBoundaryError(
                        "simulation output requires the released artifact family; "
                        f"unexpected: {entry.name}"
                    )
                if entry.is_symlink() or entry.is_dir(follow_symlinks=False):
                    raise ArtifactBoundaryError(
                        f"artifact {entry.name} requires a regular output file"
                    )
                observed.add(entry.name)
    except OSError as error:
        raise ArtifactBoundaryError(
            "artifact root requires readable released-family membership"
        ) from error
    missing = sorted(SIMULATION_ARTIFACTS - observed)
    if missing:
        raise ArtifactBoundaryError(
            "simulation output requires the released artifact family; "
            "missing: " + ", ".join(missing)
        )
    return tuple(root / name for name in sorted(observed))


def _depth_admitted_text(content: bytes) -> str:
    """Bound nested containers before JSON decoding and semantic recursion.

    The standard decoder's byte-encoding selection preserves UTF-8/16/32 and
    BOM behavior. Its parser retains syntax, duplicate-key and number authority.
    A root object/array has depth one; strings and scalar values add no depth.
    """
    text = content.decode(json.detect_encoding(content), "surrogatepass")
    depth = 0
    quoted = False
    escaped = False
    for character in text:
        if quoted:
            if escaped:
                escaped = False
            elif character == "\\":
                escaped = True
            elif character == '"':
                quoted = False
        elif character == '"':
            quoted = True
        elif character in "[{":
            depth += 1
            if depth > MAX_ARTIFACT_JSON_DEPTH:
                raise ArtifactBoundaryError(
                    f"JSON supports at most {MAX_ARTIFACT_JSON_DEPTH} nested containers"
                )
        elif character in "]}" and depth:
            depth -= 1
    return text


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


def _read_regular_file(
    path: Path, relative: str, *, maximum_bytes: int = MAX_ARTIFACT_BYTES
) -> bytes:
    no_follow = getattr(os, "O_NOFOLLOW", None)
    if not isinstance(no_follow, int) or no_follow == 0:
        raise ArtifactBoundaryError(
            "artifact verification requires platform support for fail-closed "
            "final-path no-follow opening"
        )
    nonblocking = getattr(os, "O_NONBLOCK", None)
    if not isinstance(nonblocking, int) or nonblocking == 0:
        raise ArtifactBoundaryError(
            "artifact verification requires nonblocking file acquisition support"
        )
    flags = os.O_RDONLY | no_follow | nonblocking
    try:
        descriptor = os.open(path, flags)
    except OSError as error:
        raise ArtifactBoundaryError(
            f"artifact {relative} requires a readable regular file"
        ) from error
    # Invalidate the raw reader before its descriptor can reach another owner.
    raw = None
    stream = None
    failure = None
    try:
        info = os.fstat(descriptor)
        if not stat.S_ISREG(info.st_mode):
            raise ArtifactBoundaryError(
                f"artifact {relative} requires a regular output file"
            )
        if info.st_size > maximum_bytes:
            raise ArtifactBoundaryError(
                f"artifact {relative} supports at most {maximum_bytes} bytes "
                "within the remaining family budget"
            )
        raw = io.FileIO(descriptor, "rb", closefd=False)
        stream = io.BufferedReader(raw)
        content = stream.read(maximum_bytes + 1)
        if len(content) > maximum_bytes:
            raise ArtifactBoundaryError(
                f"artifact {relative} supports at most {maximum_bytes} bytes "
                "within the remaining family budget"
            )
        return content
    except BaseException as error:
        failure = error
        raise
    finally:
        cleanups = []
        if stream is not None:
            try:
                stream.close()
            except BaseException as cleanup:
                cleanups.append(cleanup)
        if raw is not None and not raw.closed:
            try:
                raw.close()
            except BaseException as cleanup:
                cleanups.append(cleanup)
        retained = raw is not None and not raw.closed
        if not retained:
            try:
                os.close(descriptor)
            except BaseException as cleanup:
                cleanups.append(cleanup)
        if cleanups:
            cleanup = cleanups[0] if len(cleanups) == 1 else BaseExceptionGroup(
                "Artifact stream and descriptor cleanup observations", cleanups,
            )
            if retained:
                recovery = failure if failure is not None else cleanup
                recovery.retained_stream = raw
                recovery.retained_descriptor = descriptor
            if failure is None:
                raise cleanup
            failure.cleanup_error = cleanup
            failure.add_note("Artifact cleanup needs local review; the primary failure remains available.")


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
