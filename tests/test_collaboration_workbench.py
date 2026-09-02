"""Material contracts for the copy-local collaboration workbench."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import shutil
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
SPEC = importlib.util.spec_from_file_location(
    "simulation_validate_repository",
    ROOT / "tools" / "validate_repository.py",
)
assert SPEC and SPEC.loader
validation = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = validation
SPEC.loader.exec_module(validation)


class CollaborationWorkbenchTests(unittest.TestCase):
    def copy_workbench(self, destination: Path) -> None:
        shutil.copytree(ROOT / ".agents", destination / ".agents")
        shutil.copy2(ROOT / "README.md", destination / "README.md")
        shutil.copy2(ROOT / "AGENTS.md", destination / "AGENTS.md")

    def copy_living_carriers(self, destination: Path) -> None:
        for name in (
            "constellation.lock.json",
            "COORDINATION-HORIZON.json",
            "first-receipt.json",
        ):
            shutil.copy2(ROOT / name, destination / name)

    def test_copy_local_workbench_has_exact_lineage_and_routes(self) -> None:
        self.assertEqual([], validation.validate_collaboration_workbench())
        self.assertEqual(
            {
                "constellation-coherence-reconciliation",
                "contextual-jargon-scan",
                "repository-reentry",
                "source-authority-mapping",
            },
            {
                validation.parse_skill_source(ROOT / relative)[0]["name"]
                for relative in validation.PUBLIC_POSSIBLE_SKILL_METADATA
            },
        )
        self.assertTrue(
            all(
                validation.parse_skill_source(ROOT / relative)[0]["source_band"]
                == "public_possible"
                for relative in validation.PUBLIC_POSSIBLE_SKILL_METADATA
            )
        )

    def test_upstream_lineage_drift_is_visible(self) -> None:
        with tempfile.TemporaryDirectory(prefix="simulation-workbench-") as temporary:
            copy_root = Path(temporary)
            self.copy_workbench(copy_root)
            target = (
                copy_root
                / ".agents/skills/constellation-coherence-reconciliation/SKILL.md"
            )
            source = target.read_text(encoding="utf-8")
            target.write_text(
                source.replace(
                    "05357fbed16a5b5aca80c239e4c7535f67d5654b",
                    "f" * 40,
                    1,
                ),
                encoding="utf-8",
            )
            findings = validation.validate_collaboration_workbench(copy_root)
            self.assertTrue(any("metadata differs" in item for item in findings))

    def test_living_constellation_matches_accepted_comparison_state(self) -> None:
        self.assertEqual([], validation.validate_living_constellation_coherence())
        lock = json.loads((ROOT / "constellation.lock.json").read_text())
        self.assertEqual(
            lock["simulation"]["canonical_closure_digest"],
            lock["comparison"]["canonical_closure_digest"],
        )

    def test_closure_relation_divergence_is_visible(self) -> None:
        with tempfile.TemporaryDirectory(prefix="simulation-coherence-") as temporary:
            copy_root = Path(temporary)
            self.copy_living_carriers(copy_root)
            lock_path = copy_root / "constellation.lock.json"
            lock = json.loads(lock_path.read_text(encoding="utf-8"))
            lock["comparison"]["canonical_closure_digest"] = "sha256:" + "f" * 64
            lock_path.write_text(
                json.dumps(lock, indent=2) + "\n",
                encoding="utf-8",
            )
            findings = validation.validate_living_constellation_coherence(copy_root)
            self.assertIn(
                "Simulation and Comparison canonical closure relations differ",
                findings,
            )

    def test_horizon_cannot_reopen_completed_comparison_admission_silently(self) -> None:
        with tempfile.TemporaryDirectory(prefix="simulation-coherence-") as temporary:
            copy_root = Path(temporary)
            self.copy_living_carriers(copy_root)
            horizon_path = copy_root / "COORDINATION-HORIZON.json"
            horizon = json.loads(horizon_path.read_text(encoding="utf-8"))
            for item in horizon["work_items"]:
                if item["item_id"] == "HORIZON-COMPARATIVE-ADMISSION":
                    item["state"] = "active"
            horizon_path.write_text(
                json.dumps(horizon, indent=2) + "\n",
                encoding="utf-8",
            )
            findings = validation.validate_living_constellation_coherence(copy_root)
            self.assertIn(
                "accepted Comparison admission must remain complete",
                findings,
            )


if __name__ == "__main__":
    unittest.main()
