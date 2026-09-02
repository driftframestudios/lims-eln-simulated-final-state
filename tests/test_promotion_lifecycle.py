"""Focused behavior checks for the selected-future promotion carrier."""

from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path
import sys
import unittest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from lims_eln_sim.promotion_receipt import (  # noqa: E402
    PromotionReceiptError,
    canonical_digest,
    file_digest,
    validate_promotion_receipt,
)


class PromotionLifecycleTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.observed_receipt = json.loads(
            (ROOT / "receipts" / "promotion-receipt.json").read_text(
                encoding="utf-8"
            )
        )

    def observed(self) -> dict:
        return deepcopy(self.observed_receipt)

    def candidate(self) -> dict:
        receipt = self.observed()
        receipt["promotion_state"] = "candidate_ready"
        receipt["release_event_evidence"] = {
            "evidence_mode": "planned",
            "assurance_stage": "specified",
        }
        receipt["release_subject"] = None
        return receipt

    def test_observed_receipt_records_release_event_and_preserves_forecast_authority(self) -> None:
        validate_promotion_receipt(self.observed_receipt)
        self.assertEqual(
            self.observed_receipt["release_event_evidence"],
            {"evidence_mode": "observed", "assurance_stage": "verified"},
        )

    def test_schema_names_both_states_and_the_complete_observed_subject(self) -> None:
        schema = json.loads(
            (ROOT / "schemas" / "promotion-receipt.schema.json").read_text(
                encoding="utf-8"
            )
        )
        self.assertEqual(
            schema["properties"]["promotion_state"]["enum"],
            ["candidate_ready", "release_observed"],
        )
        self.assertEqual(
            schema["properties"]["target_release"]["const"],
            "forecast-2028-FR-v1",
        )
        self.assertEqual(
            set(schema["$defs"]["observedReleaseSubject"]["required"]),
            {
                "git_object_format",
                "tag",
                "tag_object_oid",
                "commit_oid",
                "tree_oid",
                "archive_format",
                "archive_digest",
                "promoted_at",
                "tag_signature_verification",
                "hosted_check_contexts",
                "local_verification_signals",
            },
        )
        self.assertIsNotNone(self.observed_receipt["release_subject"])
        self.assertEqual(
            self.observed_receipt["forecast_authority"],
            {
                "evidence_mode": "simulated",
                "assurance_stage": "verified",
                "simulation_authority": (
                    "definitive_within_selected_future_reality"
                ),
                "environment_observed_closure": "separate_unasserted_state",
                "production_authorization_effect": "none",
            },
        )

    def test_observed_release_requires_complete_immutable_subject(self) -> None:
        receipt = self.observed()
        validate_promotion_receipt(receipt)

        mutations = (
            (
                "missing-tree",
                lambda value: value["release_subject"].pop("tree_oid"),
                "release_subject carries exactly",
            ),
            (
                "unsigned-tag",
                lambda value: value["release_subject"].__setitem__(
                    "tag_signature_verification", "unverified"
                ),
                "tag_signature_verification",
            ),
            (
                "zero-archive",
                lambda value: value["release_subject"].__setitem__(
                    "archive_digest", "sha256:" + "0" * 64
                ),
                "nonzero SHA-256",
            ),
            (
                "undated-promotion",
                lambda value: value["release_subject"].__setitem__(
                    "promoted_at", "2026-09-02T04:00:00"
                ),
                "explicit UTC offset",
            ),
            (
                "duplicate-check",
                lambda value: value["release_subject"][
                    "hosted_check_contexts"
                ].append(
                    deepcopy(
                        value["release_subject"]["hosted_check_contexts"][0]
                    )
                ),
                "check names and run IDs unique",
            ),
        )
        for name, mutate, message in mutations:
            with self.subTest(name=name):
                changed = deepcopy(receipt)
                mutate(changed)
                with self.assertRaisesRegex(PromotionReceiptError, message):
                    validate_promotion_receipt(changed)

    def test_release_event_observation_does_not_reclassify_forecast_evidence(self) -> None:
        observed = self.observed()
        observed["forecast_authority"]["evidence_mode"] = "observed"
        with self.assertRaisesRegex(
            PromotionReceiptError,
            "forecast_authority preserves simulated evidence",
        ):
            validate_promotion_receipt(observed)

        candidate_with_subject = self.candidate()
        candidate_with_subject["release_subject"] = self.observed()[
            "release_subject"
        ]
        with self.assertRaisesRegex(PromotionReceiptError, "keeps release_subject null"):
            validate_promotion_receipt(candidate_with_subject)

    def test_release_manifest_binds_schema_and_observed_receipt(self) -> None:
        manifest = json.loads(
            (ROOT / "release" / "repository-role.json").read_text(encoding="utf-8")
        )
        binding = manifest["promotion_receipt_contract"]
        schema_path = ROOT / binding["schema_path"]
        receipt_path = ROOT / binding["receipt_path"]
        receipt = json.loads(receipt_path.read_text(encoding="utf-8"))

        self.assertEqual(binding["schema_version"], receipt["schema_version"])
        self.assertEqual(binding["schema_file_sha256"], file_digest(schema_path))
        self.assertEqual(
            binding["receipt_canonical_json_digest"], canonical_digest(receipt)
        )
        self.assertEqual(
            manifest["release_coordinates"]["promotion_receipt_id"],
            receipt["promotion_receipt_id"],
        )
        self.assertEqual(
            manifest["release_coordinates"]["coordinate_status"],
            "release_observed",
        )


if __name__ == "__main__":
    unittest.main()
