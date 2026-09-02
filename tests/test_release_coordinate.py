"""Focused checks for the signed Simulation release coordinate."""

from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from lims_eln_sim.release_coordinate import (  # noqa: E402
    EXPECTED_HOSTED_CHECK_CONTEXTS,
    ReleaseCoordinateError,
    observe_release_coordinate,
    verify_release_coordinate,
)


class SignedRepository:
    """Create one isolated signed-tag repository for behavior checks."""

    def __init__(self) -> None:
        self.temporary = tempfile.TemporaryDirectory(prefix="release-coordinate-")
        self.root = Path(self.temporary.name)
        self.private_key = self.root / "release-signing-key"
        self.public_key = self.root / "release-signing-key.pub"
        self.trusted_signers = self.root / "release" / "trusted-release-signers"
        self._receipt: dict | None = None
        self._run("init", "--initial-branch=main")
        self._run("config", "user.name", "Release Test")
        self._run("config", "user.email", "release@example.invalid")
        subprocess.run(
            [
                "ssh-keygen",
                "-q",
                "-t",
                "ed25519",
                "-N",
                "",
                "-f",
                str(self.private_key),
            ],
            check=True,
            capture_output=True,
        )
        fingerprint = subprocess.run(
            ["ssh-keygen", "-lf", str(self.public_key)],
            check=True,
            capture_output=True,
            text=True,
        ).stdout.split()
        self.signing_fingerprint = fingerprint[1]
        self._run("config", "gpg.format", "ssh")
        self._run("config", "user.signingkey", str(self.private_key))
        (self.root / "README.md").write_text("selected future\n", encoding="utf-8")
        self._run("add", "README.md")
        self._run("commit", "-m", "Release selected future")
        self._run("update-ref", "refs/remotes/origin/main", "HEAD")
        self._run(
            "tag",
            "-s",
            "-m",
            "Release simulated final state",
            "forecast-2028-FR-v1",
        )
        self._write_trusted_signers(self.public_key)

    def close(self) -> None:
        self.temporary.cleanup()

    def _run(self, *arguments: str) -> str:
        result = subprocess.run(
            ["git", *arguments],
            cwd=self.root,
            check=True,
            capture_output=True,
            text=True,
        )
        return result.stdout.strip()

    def _write_trusted_signers(self, public_key: Path) -> None:
        key_parts = public_key.read_text(encoding="utf-8").split()
        self.trusted_signers.parent.mkdir(exist_ok=True)
        self.trusted_signers.write_text(
            "release@example.invalid namespaces=\"git\" "
            f"{key_parts[0]} {key_parts[1]}\n",
            encoding="utf-8",
        )

    def coordinate(self):
        return observe_release_coordinate(
            repository=self.root,
            tag="forecast-2028-FR-v1",
            expected_signing_fingerprint=self.signing_fingerprint,
        )

    def observed_receipt(self) -> dict:
        if self._receipt is not None:
            return deepcopy(self._receipt)
        receipt = json.loads(
            (ROOT / "receipts" / "promotion-receipt.json").read_text(
                encoding="utf-8"
            )
        )
        coordinate = self.coordinate()
        receipt["promotion_state"] = "release_observed"
        receipt["release_event_evidence"] = {
            "evidence_mode": "observed",
            "assurance_stage": "verified",
        }
        receipt["release_subject"] = {
            **coordinate.as_dict(),
            "hosted_check_contexts": [
                dict(context) for context in EXPECTED_HOSTED_CHECK_CONTEXTS
            ],
            "local_verification_signals": [
                "complete regression suite passed",
                "signed release coordinate reproduced locally",
            ],
        }
        receipt_path = self.root / "receipts" / "promotion-receipt.json"
        receipt_path.parent.mkdir(exist_ok=True)
        receipt_path.write_text(
            json.dumps(receipt, indent=2) + "\n",
            encoding="utf-8",
        )
        manifest_path = self.root / "release" / "repository-role.json"
        manifest_path.write_text(
            json.dumps(
                {
                    "release_coordinates": {
                        "reviewed_candidate_commit": coordinate.commit_oid,
                        "reviewed_candidate_tree_digest": (
                            "git-tree-sha1:" + coordinate.tree_oid
                        ),
                        "accepted_commit": coordinate.commit_oid,
                        "accepted_tree_digest": (
                            "git-tree-sha1:" + coordinate.tree_oid
                        ),
                        "tag_object_oid": coordinate.tag_object_oid,
                        "archive_digest": coordinate.archive_digest,
                    }
                },
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
        self._run(
            "add",
            "receipts/promotion-receipt.json",
            "release/repository-role.json",
        )
        self._run("commit", "-m", "Record release observation")
        self._run("update-ref", "refs/remotes/origin/main", "HEAD")
        self._receipt = receipt
        return deepcopy(receipt)


class ReleaseCoordinateTests(unittest.TestCase):
    def setUp(self) -> None:
        self.repository = SignedRepository()

    def tearDown(self) -> None:
        self.repository.close()

    def test_observed_receipt_matches_signed_release_objects_and_archive(self) -> None:
        receipt = self.repository.observed_receipt()
        self.assertIsNone(
            verify_release_coordinate(
                self.repository.root,
                receipt,
                expected_signing_fingerprint=(
                    self.repository.signing_fingerprint
                ),
            )
        )
        coordinate = self.repository.coordinate()

        self.assertEqual(
            self.repository._run(
                "rev-parse", "refs/tags/forecast-2028-FR-v1^{tag}"
            ),
            coordinate.tag_object_oid,
        )
        self.assertEqual(
            self.repository._run(
                "rev-parse", "refs/tags/forecast-2028-FR-v1^{commit}"
            ),
            coordinate.commit_oid,
        )
        self.assertEqual("valid", coordinate.tag_signature_verification)

    def test_receipt_difference_names_the_exact_git_coordinate_field(self) -> None:
        receipt = self.repository.observed_receipt()
        receipt["release_subject"]["archive_digest"] = "sha256:" + "7" * 64

        with self.assertRaisesRegex(
            ReleaseCoordinateError,
            "archive_digest: receipt=.*derived=",
        ):
            verify_release_coordinate(
                self.repository.root,
                receipt,
                expected_signing_fingerprint=(
                    self.repository.signing_fingerprint
                ),
            )

    def test_hosted_contexts_are_the_accepted_run_observations(self) -> None:
        receipt = self.repository.observed_receipt()
        receipt["release_subject"]["hosted_check_contexts"][0]["run_id"] = (
            "33589999999"
        )

        with self.assertRaisesRegex(
            ReleaseCoordinateError,
            "accepted hosted check contexts and run IDs",
        ):
            verify_release_coordinate(
                self.repository.root,
                receipt,
                expected_signing_fingerprint=(
                    self.repository.signing_fingerprint
                ),
            )

    def test_reviewed_candidate_and_accepted_release_share_one_tree(self) -> None:
        receipt = self.repository.observed_receipt()
        manifest_path = self.repository.root / "release" / "repository-role.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        manifest["release_coordinates"]["reviewed_candidate_tree_digest"] = (
            "git-tree-sha1:" + "7" * 40
        )
        manifest_path.write_text(
            json.dumps(manifest, indent=2) + "\n",
            encoding="utf-8",
        )

        with self.assertRaisesRegex(
            ReleaseCoordinateError,
            "reviewed candidate and accepted Git tree",
        ):
            verify_release_coordinate(
                self.repository.root,
                receipt,
                expected_signing_fingerprint=(
                    self.repository.signing_fingerprint
                ),
            )

    def test_trust_carrier_includes_the_expected_signing_fingerprint(self) -> None:
        receipt = self.repository.observed_receipt()
        other_private_key = self.repository.root / "other-signing-key"
        subprocess.run(
            [
                "ssh-keygen",
                "-q",
                "-t",
                "ed25519",
                "-N",
                "",
                "-f",
                str(other_private_key),
            ],
            check=True,
            capture_output=True,
        )
        self.repository._write_trusted_signers(
            self.repository.root / "other-signing-key.pub"
        )

        with self.assertRaisesRegex(
            ReleaseCoordinateError,
            "exactly the expected signing-key fingerprint",
        ):
            verify_release_coordinate(
                self.repository.root,
                receipt,
                expected_signing_fingerprint=(
                    self.repository.signing_fingerprint
                ),
            )

    def test_trust_carrier_rejects_an_additional_signing_key(self) -> None:
        receipt = self.repository.observed_receipt()
        other_private_key = self.repository.root / "other-allowed-signing-key"
        subprocess.run(
            [
                "ssh-keygen",
                "-q",
                "-t",
                "ed25519",
                "-N",
                "",
                "-f",
                str(other_private_key),
            ],
            check=True,
            capture_output=True,
        )
        key_parts = (
            self.repository.root / "other-allowed-signing-key.pub"
        ).read_text(encoding="utf-8").split()
        with self.repository.trusted_signers.open("a", encoding="utf-8") as signers:
            signers.write(
                "alternate@example.invalid namespaces=\"git\" "
                f"{key_parts[0]} {key_parts[1]}\n"
            )

        with self.assertRaisesRegex(
            ReleaseCoordinateError,
            "exactly the expected signing-key fingerprint",
        ):
            verify_release_coordinate(
                self.repository.root,
                receipt,
                expected_signing_fingerprint=(
                    self.repository.signing_fingerprint
                ),
            )

    def test_current_carrier_retains_the_exact_observed_receipt(self) -> None:
        receipt = self.repository.observed_receipt()
        receipt_path = (
            self.repository.root / "receipts" / "promotion-receipt.json"
        )
        receipt_path.write_bytes(receipt_path.read_bytes() + b"\n")

        with self.assertRaisesRegex(
            ReleaseCoordinateError,
            "exact promotion-receipt bytes",
        ):
            verify_release_coordinate(
                self.repository.root,
                receipt,
                expected_signing_fingerprint=(
                    self.repository.signing_fingerprint
                ),
            )

    def test_release_ref_is_direct_annotated_tag_in_accepted_history(self) -> None:
        receipt = self.repository.observed_receipt()
        self.repository._run("tag", "-d", "forecast-2028-FR-v1")
        self.repository._run("tag", "forecast-2028-FR-v1", "HEAD")
        with self.assertRaisesRegex(ReleaseCoordinateError, "annotated tag object"):
            verify_release_coordinate(
                self.repository.root,
                receipt,
                expected_signing_fingerprint=(
                    self.repository.signing_fingerprint
                ),
            )

        self.repository._run("tag", "-d", "forecast-2028-FR-v1")
        self.repository._run(
            "tag",
            "-s",
            "-m",
            "Release simulated final state",
            "forecast-2028-FR-v1",
        )
        orphan = self.repository._run(
            "commit-tree",
            self.repository._run("rev-parse", "HEAD^{tree}"),
            "-m",
            "Independent history",
        )
        self.repository._run("update-ref", "refs/remotes/origin/main", orphan)
        with self.assertRaisesRegex(ReleaseCoordinateError, "accepted history"):
            verify_release_coordinate(
                self.repository.root,
                receipt,
                expected_signing_fingerprint=(
                    self.repository.signing_fingerprint
                ),
            )

    def test_candidate_receipt_preserves_the_open_promotion_boundary(self) -> None:
        candidate = self.repository.observed_receipt()
        candidate["promotion_state"] = "candidate_ready"
        candidate["release_event_evidence"] = {
            "evidence_mode": "planned",
            "assurance_stage": "specified",
        }
        candidate["release_subject"] = None
        with self.assertRaisesRegex(
            ReleaseCoordinateError,
            "after promotion_state is release_observed",
        ):
            verify_release_coordinate(
                self.repository.root,
                deepcopy(candidate),
                expected_signing_fingerprint=(
                    self.repository.signing_fingerprint
                ),
            )


if __name__ == "__main__":
    unittest.main()
