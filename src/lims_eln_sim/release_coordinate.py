"""Verify one observed Simulation release against local Git objects."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import base64
from hashlib import sha256
import json
from pathlib import Path
import shlex
import subprocess
import tempfile
from typing import Any, Mapping

from .promotion_receipt import validate_promotion_receipt


DEFAULT_ACCEPTED_REF = "refs/remotes/origin/main"
DEFAULT_TRUSTED_SIGNERS = Path("release/trusted-release-signers")
EXPECTED_SIGNING_FINGERPRINT = (
    "SHA256:86lsl/VvHgab8NoMoFDtIeJMZIhzOQ/yyqe2C8mkNhU"
)
EXPECTED_HOSTED_CHECK_CONTEXTS = (
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
)
_DERIVED_SUBJECT_FIELDS = (
    "git_object_format",
    "tag",
    "tag_object_oid",
    "commit_oid",
    "tree_oid",
    "archive_format",
    "archive_digest",
    "promoted_at",
    "tag_signature_verification",
)


class ReleaseCoordinateError(ValueError):
    """Return a release coordinate to its observable verification path."""


@dataclass(frozen=True)
class ReleaseCoordinate:
    """The locally reproducible portion of an observed release subject."""

    git_object_format: str
    tag: str
    tag_object_oid: str
    commit_oid: str
    tree_oid: str
    archive_format: str
    archive_digest: str
    promoted_at: str
    tag_signature_verification: str

    def as_dict(self) -> dict[str, str]:
        """Return fields using the promotion-receipt vocabulary."""
        return {
            field: getattr(self, field) for field in _DERIVED_SUBJECT_FIELDS
        }


def observe_release_coordinate(
    *,
    repository: Path,
    tag: str,
    trusted_signers: Path = DEFAULT_TRUSTED_SIGNERS,
    accepted_ref: str = DEFAULT_ACCEPTED_REF,
    expected_signing_fingerprint: str = EXPECTED_SIGNING_FINGERPRINT,
) -> ReleaseCoordinate:
    """Derive and cryptographically verify one repository release coordinate."""
    root = _repository_root(repository)
    signer_path = _trusted_signer_path(
        root,
        trusted_signers,
        expected_signing_fingerprint,
    )
    tag_ref = _tag_ref(tag)

    object_format = _git_text(root, "rev-parse", "--show-object-format")
    if object_format != "sha1":
        raise ReleaseCoordinateError(
            f"release repository object format is sha1; observed {object_format!r}"
        )

    object_type = _git_text(root, "cat-file", "-t", tag_ref)
    if object_type != "tag":
        raise ReleaseCoordinateError(
            f"release ref {tag_ref!r} identifies a direct annotated tag object"
        )

    tag_object_oid = _git_text(root, "rev-parse", "--verify", tag_ref)
    tag_headers = _tag_headers(_git_text(root, "cat-file", "-p", tag_ref), tag_ref)
    if tag_headers.get("type") != "commit":
        raise ReleaseCoordinateError(
            f"release tag {tag_ref!r} directly identifies a commit object"
        )
    if tag_headers.get("tag") != tag:
        raise ReleaseCoordinateError(
            f"release tag payload names {tag!r}; observed {tag_headers.get('tag')!r}"
        )

    commit_oid = _git_text(root, "rev-parse", "--verify", f"{tag_ref}^{{commit}}")
    if tag_headers.get("object") != commit_oid:
        raise ReleaseCoordinateError(
            "release tag payload and peeled commit identify one Git object"
        )
    tree_oid = _git_text(root, "rev-parse", "--verify", f"{commit_oid}^{{tree}}")

    accepted_commit = _git_text(
        root, "rev-parse", "--verify", f"{accepted_ref}^{{commit}}"
    )
    ancestry = _run_git(
        root,
        "merge-base",
        "--is-ancestor",
        commit_oid,
        accepted_commit,
    )
    if ancestry.returncode == 1:
        raise ReleaseCoordinateError(
            f"release commit {commit_oid} is outside accepted history {accepted_ref}"
        )
    if ancestry.returncode != 0:
        raise ReleaseCoordinateError(
            _command_failure("git merge-base --is-ancestor", ancestry)
        )

    _verify_tag_signature(root, tag_ref, signer_path)
    tagger_epoch = _tagger_epoch(root, tag_ref)
    promoted_at = (
        datetime.fromtimestamp(tagger_epoch, timezone.utc)
        .isoformat(timespec="seconds")
        .replace("+00:00", "Z")
    )
    archive_digest = _archive_digest(root, commit_oid)

    return ReleaseCoordinate(
        git_object_format=object_format,
        tag=tag,
        tag_object_oid=tag_object_oid,
        commit_oid=commit_oid,
        tree_oid=tree_oid,
        archive_format="git-tar",
        archive_digest=archive_digest,
        promoted_at=promoted_at,
        tag_signature_verification="valid",
    )


def verify_release_coordinate(
    root: Path,
    receipt: Mapping[str, Any],
    *,
    expected_signing_fingerprint: str = EXPECTED_SIGNING_FINGERPRINT,
) -> None:
    """Require an observed receipt to match its signed local Git coordinate."""
    validate_promotion_receipt(receipt)
    if receipt["promotion_state"] != "release_observed":
        raise ReleaseCoordinateError(
            "release-coordinate verification begins after promotion_state is release_observed"
        )
    subject = receipt["release_subject"]
    if tuple(subject["hosted_check_contexts"]) != EXPECTED_HOSTED_CHECK_CONTEXTS:
        raise ReleaseCoordinateError(
            "release receipt retains the accepted hosted check contexts and run IDs"
        )

    coordinate = observe_release_coordinate(
        repository=root,
        tag=receipt["target_release"],
        expected_signing_fingerprint=expected_signing_fingerprint,
    )
    differences: dict[str, dict[str, str]] = {}
    for field, observed in coordinate.as_dict().items():
        expected = subject[field]
        if field == "promoted_at":
            matches = _instant(expected) == _instant(observed)
        else:
            matches = expected == observed
        if not matches:
            differences[field] = {
                "receipt": expected,
                "derived": observed,
            }
    if differences:
        summary = "; ".join(
            f"{field}: receipt={values['receipt']!r}, derived={values['derived']!r}"
            for field, values in sorted(differences.items())
        )
        raise ReleaseCoordinateError(
            "promotion receipt differs from the signed Git release coordinate: "
            + summary
        )
    _verify_release_manifest_bindings(root.resolve(), coordinate)
    _verify_observation_carrier(root.resolve(), receipt, coordinate.commit_oid)
    return None


def _verify_release_manifest_bindings(
    repository: Path,
    coordinate: ReleaseCoordinate,
) -> None:
    manifest_path = repository / "release" / "repository-role.json"
    try:
        manifest = json.loads(manifest_path.read_bytes())
        declared = manifest["release_coordinates"]
    except (OSError, UnicodeDecodeError, json.JSONDecodeError, KeyError, TypeError) as error:
        raise ReleaseCoordinateError(
            "release manifest carries the observed release coordinates"
        ) from error

    required_fields = {
        "reviewed_candidate_commit",
        "reviewed_candidate_tree_digest",
        "accepted_commit",
        "accepted_tree_digest",
        "tag_object_oid",
        "archive_digest",
    }
    if not required_fields.issubset(declared):
        raise ReleaseCoordinateError(
            "release manifest carries reviewed-candidate and accepted-release bindings"
        )

    candidate_commit = declared["reviewed_candidate_commit"]
    candidate_tree = _git_text(
        repository,
        "rev-parse",
        "--verify",
        f"{candidate_commit}^{{tree}}",
    )
    expected = {
        "reviewed_candidate_tree_digest": f"git-tree-sha1:{candidate_tree}",
        "accepted_commit": coordinate.commit_oid,
        "accepted_tree_digest": f"git-tree-sha1:{coordinate.tree_oid}",
        "tag_object_oid": coordinate.tag_object_oid,
        "archive_digest": coordinate.archive_digest,
    }
    differences = {
        field: {"manifest": declared.get(field), "derived": value}
        for field, value in expected.items()
        if declared.get(field) != value
    }
    if candidate_tree != coordinate.tree_oid:
        differences["reviewed_candidate_and_accepted_tree"] = {
            "manifest": candidate_tree,
            "derived": coordinate.tree_oid,
        }
    if differences:
        summary = "; ".join(
            f"{field}: manifest={values['manifest']!r}, derived={values['derived']!r}"
            for field, values in sorted(differences.items())
        )
        raise ReleaseCoordinateError(
            "release manifest differs from the reviewed candidate and accepted Git tree: "
            + summary
        )


def _verify_observation_carrier(
    repository: Path,
    receipt: Mapping[str, Any],
    release_commit: str,
) -> None:
    carrier_commit = _git_text(repository, "rev-parse", "--verify", "HEAD^{commit}")
    ancestry = _run_git(
        repository,
        "merge-base",
        "--is-ancestor",
        release_commit,
        carrier_commit,
    )
    if ancestry.returncode == 1:
        raise ReleaseCoordinateError(
            f"release commit {release_commit} is outside observation carrier HEAD history"
        )
    if ancestry.returncode != 0:
        raise ReleaseCoordinateError(
            _command_failure("git merge-base --is-ancestor", ancestry)
        )

    receipt_path = repository / "receipts" / "promotion-receipt.json"
    if receipt_path.is_symlink() or not receipt_path.is_file():
        raise ReleaseCoordinateError(
            "observation carrier uses a regular promotion-receipt file"
        )
    working_bytes = receipt_path.read_bytes()
    try:
        working_receipt = json.loads(working_bytes)
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ReleaseCoordinateError(
            "working promotion receipt carries valid UTF-8 JSON"
        ) from error
    if working_receipt != receipt:
        raise ReleaseCoordinateError(
            "selected promotion receipt matches the working receipt carrier"
        )
    carrier = subprocess.run(
        ["git", "show", f"{carrier_commit}:receipts/promotion-receipt.json"],
        cwd=repository,
        check=False,
        capture_output=True,
    )
    if carrier.returncode != 0:
        diagnostic = carrier.stderr.decode("utf-8", errors="replace").strip()
        raise ReleaseCoordinateError(
            "observation carrier HEAD contains the promotion receipt: "
            + (diagnostic or "no diagnostic")
        )
    if carrier.stdout != working_bytes:
        raise ReleaseCoordinateError(
            "observation carrier HEAD and the working tree contain exact promotion-receipt bytes"
        )


def _repository_root(repository: Path) -> Path:
    root = repository.resolve()
    if not root.is_dir():
        raise ReleaseCoordinateError(f"repository path is a directory: {root}")
    result = _run_git(root, "rev-parse", "--show-toplevel")
    if result.returncode != 0:
        raise ReleaseCoordinateError(_command_failure("git rev-parse", result))
    observed = Path(result.stdout.strip()).resolve()
    if observed != root:
        raise ReleaseCoordinateError(
            f"repository path identifies its Git top level: expected {root}, observed {observed}"
        )
    return root


def _trusted_signer_path(
    repository: Path,
    path: Path,
    expected_fingerprint: str,
) -> Path:
    candidate = path if path.is_absolute() else repository / path
    if candidate.is_symlink():
        raise ReleaseCoordinateError(
            "trusted release signers use a repository-owned regular file"
        )
    try:
        resolved = candidate.resolve(strict=True)
        resolved.relative_to(repository)
    except (FileNotFoundError, ValueError) as error:
        raise ReleaseCoordinateError(
            "trusted release signers use a repository-owned regular file"
        ) from error
    if not resolved.is_file():
        raise ReleaseCoordinateError(
            "trusted release signers use a repository-owned regular file"
        )
    active_lines = [
        line.strip()
        for line in resolved.read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    ]
    if not active_lines:
        raise ReleaseCoordinateError(
            "trusted release signers name at least one Git-scoped public key"
        )
    if any('namespaces="git"' not in line for line in active_lines):
        raise ReleaseCoordinateError(
            "trusted release signers scope each public key to the Git namespace"
        )
    fingerprints = {_ssh_fingerprint(line) for line in active_lines}
    if expected_fingerprint not in fingerprints:
        raise ReleaseCoordinateError(
            "trusted release signers include the expected signing-key fingerprint: "
            f"{expected_fingerprint}"
        )
    return resolved


def _ssh_fingerprint(allowed_signer: str) -> str:
    try:
        fields = shlex.split(allowed_signer)
    except ValueError as error:
        raise ReleaseCoordinateError(
            "trusted release signers use valid OpenSSH allowed-signers syntax"
        ) from error
    key_index = next(
        (
            index
            for index, field in enumerate(fields)
            if field.startswith(("ssh-", "ecdsa-", "sk-"))
        ),
        -1,
    )
    if key_index < 1 or key_index + 1 >= len(fields):
        raise ReleaseCoordinateError(
            "trusted release signers carry an OpenSSH public key"
        )
    try:
        key_blob = base64.b64decode(fields[key_index + 1], validate=True)
    except (ValueError, base64.binascii.Error) as error:
        raise ReleaseCoordinateError(
            "trusted release signers carry a valid OpenSSH public key"
        ) from error
    encoded = base64.b64encode(sha256(key_blob).digest()).decode("ascii")
    return "SHA256:" + encoded.rstrip("=")


def _tag_ref(tag: str) -> str:
    if not tag or any(character.isspace() for character in tag):
        raise ReleaseCoordinateError("release tag is a complete Git ref segment")
    return f"refs/tags/{tag}"


def _tag_headers(payload: str, tag_ref: str) -> dict[str, str]:
    header_block, separator, _message = payload.partition("\n\n")
    if not separator:
        raise ReleaseCoordinateError(
            f"release tag {tag_ref!r} carries an annotated tag payload"
        )
    headers: dict[str, str] = {}
    for line in header_block.splitlines():
        field, separator, value = line.partition(" ")
        if not separator or field in headers:
            raise ReleaseCoordinateError(
                f"release tag {tag_ref!r} carries unambiguous object headers"
            )
        headers[field] = value
    required = {"object", "type", "tag", "tagger"}
    if not required.issubset(headers):
        raise ReleaseCoordinateError(
            f"release tag {tag_ref!r} carries object, type, tag, and tagger headers"
        )
    return headers


def _tagger_epoch(repository: Path, tag_ref: str) -> int:
    raw = _git_text(
        repository,
        "for-each-ref",
        "--format=%(taggerdate:unix)",
        tag_ref,
    )
    try:
        epoch = int(raw)
    except ValueError as error:
        raise ReleaseCoordinateError(
            f"release tag {tag_ref!r} carries an exact tagger instant"
        ) from error
    if epoch <= 0:
        raise ReleaseCoordinateError(
            f"release tag {tag_ref!r} carries an exact tagger instant"
        )
    return epoch


def _verify_tag_signature(
    repository: Path, tag_ref: str, trusted_signers: Path
) -> None:
    result = _run_git(
        repository,
        "-c",
        "gpg.format=ssh",
        "-c",
        "gpg.minTrustLevel=fully",
        "-c",
        f"gpg.ssh.allowedSignersFile={trusted_signers}",
        "verify-tag",
        "--raw",
        tag_ref,
    )
    if result.returncode != 0:
        raise ReleaseCoordinateError(
            "release tag has a valid signature from a repository-trusted signer: "
            + _diagnostic(result)
        )


def _archive_digest(repository: Path, commit_oid: str) -> str:
    command = [
        "git",
        "-c",
        "tar.umask=0002",
        "archive",
        "--format=tar",
        commit_oid,
    ]
    digest = sha256()
    with tempfile.TemporaryFile(prefix="release-archive-") as archive:
        result = subprocess.run(
            command,
            cwd=repository,
            check=False,
            stdout=archive,
            stderr=subprocess.PIPE,
        )
        stderr = result.stderr.decode("utf-8", errors="replace").strip()
        returncode = result.returncode
        archive.seek(0)
        for block in iter(lambda: archive.read(1024 * 1024), b""):
            digest.update(block)
    if returncode != 0:
        raise ReleaseCoordinateError(
            f"git archive exited with {returncode}: {stderr or '<no diagnostic>'}"
        )
    return f"sha256:{digest.hexdigest()}"


def _instant(value: str) -> datetime:
    try:
        instant = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (AttributeError, ValueError) as error:
        raise ReleaseCoordinateError(
            f"release promotion instant is valid ISO 8601: {value!r}"
        ) from error
    if instant.tzinfo is None or instant.utcoffset() is None:
        raise ReleaseCoordinateError(
            f"release promotion instant has an explicit UTC offset: {value!r}"
        )
    return instant.astimezone(timezone.utc)


def _git_text(repository: Path, *arguments: str) -> str:
    result = _run_git(repository, *arguments)
    if result.returncode != 0:
        raise ReleaseCoordinateError(
            _command_failure("git " + " ".join(arguments), result)
        )
    return result.stdout.strip()


def _run_git(
    repository: Path,
    *arguments: str,
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *arguments],
        cwd=repository,
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )


def _diagnostic(result: subprocess.CompletedProcess[str]) -> str:
    return result.stderr.strip() or result.stdout.strip() or "no diagnostic"


def _command_failure(
    command: str, result: subprocess.CompletedProcess[str]
) -> str:
    return (
        f"{command} exited with {result.returncode}: "
        f"{_diagnostic(result)}"
    )
