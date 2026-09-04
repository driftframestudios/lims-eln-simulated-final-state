"""Focused checks for accepted sibling coordinates and receiving work."""

from __future__ import annotations

from copy import deepcopy
import importlib.util
import json
from pathlib import Path
import sys
import unittest


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "simulation_check_living_constellation",
    ROOT / "tools" / "check_living_constellation.py",
)
assert SPEC and SPEC.loader
checker = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = checker
SPEC.loader.exec_module(checker)


class LivingConstellationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.constellation = json.loads(
            (ROOT / "constellation.lock.json").read_text(encoding="utf-8")
        )
        cls.horizon = json.loads(
            (ROOT / "COORDINATION-HORIZON.json").read_text(encoding="utf-8")
        )
        cls.first_receipt = json.loads(
            (ROOT / "first-receipt.json").read_text(encoding="utf-8")
        )
        cls.release_role = json.loads(
            (ROOT / "release/repository-role.json").read_text(encoding="utf-8")
        )
        cls.closure_digest = cls.release_role["reference_closure_digest"]

    def validate(
        self,
        constellation: dict,
        horizon: dict,
        first_receipt: dict | None = None,
    ) -> list[str]:
        return checker.validate_living_constellation(
            constellation,
            horizon,
            self.first_receipt if first_receipt is None else first_receipt,
            self.closure_digest,
        )

    def test_current_living_carriers_match_accepted_coordinates(self) -> None:
        self.assertEqual([], self.validate(self.constellation, self.horizon))
        self.assertEqual("0.3.2", self.constellation["constellation_version"])
        self.assertEqual("0.3.1", self.release_role["repository_release"])

    def test_implementation_release_identity_difference_is_visible(self) -> None:
        changed = deepcopy(self.constellation)
        changed["implementation"]["tag_object_oid"] = "0" * 40
        self.assertIn(
            "Implementation coordinate differs from accepted v0.3.2",
            self.validate(changed, self.horizon),
        )

    def test_comparison_observation_report_and_publication_differences_are_visible(
        self,
    ) -> None:
        mutations = (
            ("observation_carrier", "commit"),
            ("golden_specimen_report", "report_digest"),
            ("publication", "source_revision"),
            ("publication", "projection_manifest_sha256"),
        )
        for section, field in mutations:
            with self.subTest(section=section, field=field):
                changed = deepcopy(self.constellation)
                changed["comparison"][section][field] = "changed"
                self.assertIn(
                    "Comparison coordinate family differs from accepted "
                    "comparison-v0.3.2",
                    self.validate(changed, self.horizon),
                )

    def test_selected_future_closure_relationship_difference_is_visible(self) -> None:
        changed = deepcopy(self.constellation)
        changed["simulation"]["canonical_closure_digest"] = "sha256:" + "0" * 64
        self.assertIn(
            "Simulation coordinate differs from the retained canonical closure",
            self.validate(changed, self.horizon),
        )

    def test_receiving_horizon_differences_are_visible(self) -> None:
        mutations = (
            ("current", "Coordination Horizon current receiver"),
            ("state", "Coordination Horizon states"),
            (
                "owner",
                "scientific mapping work item differs from its accountable owner",
            ),
            (
                "dependency",
                "scientific mapping work item differs from its Comparison dependency",
            ),
        )
        for mutation, expected in mutations:
            with self.subTest(mutation=mutation):
                changed = deepcopy(self.horizon)
                mapping = next(
                    item
                    for item in changed["work_items"]
                    if item["item_id"] == "HORIZON-ACCOUNTABLE-SCIENTIFIC-MAPPING"
                )
                if mutation == "current":
                    changed["current_item_ids"] = ["HORIZON-SIMULATION-EXTENSIONS"]
                elif mutation == "state":
                    mapping["state"] = "complete"
                elif mutation == "owner":
                    mapping["owner_role"] = "simulation stewardship"
                else:
                    mapping["dependency_ids"] = []
                findings = self.validate(self.constellation, changed)
                self.assertTrue(
                    any(expected in finding for finding in findings)
                )

    def test_first_receipt_tracks_the_current_horizon_and_receiver(self) -> None:
        changed = deepcopy(self.first_receipt)
        changed["handoff"]["recipient_role"] = "comparative evidence stewardship"
        self.assertIn(
            "First Receipt handoff differs from the current receiver",
            self.validate(self.constellation, self.horizon, changed),
        )

        changed = deepcopy(self.first_receipt)
        changed["handoff"]["action_ids"] = ["HORIZON-SIMULATION-EXTENSIONS"]
        self.assertIn(
            "First Receipt handoff differs from the current action",
            self.validate(self.constellation, self.horizon, changed),
        )

        changed = deepcopy(self.first_receipt)
        changed["metadata"]["updated_at"] = "2026-09-04T06:25:05Z"
        self.assertIn(
            "living orientation timestamps do not describe one current state",
            self.validate(self.constellation, self.horizon, changed),
        )

    def test_first_receipt_resolves_exact_sibling_coordinates_through_lock(
        self,
    ) -> None:
        changed = deepcopy(self.first_receipt)
        source = next(
            item
            for item in changed["source_permissions"]
            if item["source"].startswith("accepted Comparison")
        )
        source["verification"] = "Use the accepted comparison result."
        findings = self.validate(self.constellation, self.horizon, changed)
        self.assertTrue(
            any(
                "accepted Comparison v0.3.2" in finding
                and "living lock" in finding
                for finding in findings
            )
        )

    def test_comparison_horizon_resolves_exact_coordinates_through_lock(self) -> None:
        changed = deepcopy(self.horizon)
        comparison = next(
            item
            for item in changed["work_items"]
            if item["item_id"] == "HORIZON-COMPARATIVE-ADMISSION"
        )
        comparison["entry_evidence"] = [
            item
            for item in comparison["entry_evidence"]
            if "constellation.lock.json" not in item
        ]
        comparison["completion_evidence"] = [
            item
            for item in comparison["completion_evidence"]
            if "constellation.lock.json" not in item
        ]
        self.assertIn(
            "Coordination Horizon does not resolve Comparison through the living lock",
            self.validate(self.constellation, changed),
        )


if __name__ == "__main__":
    unittest.main()
