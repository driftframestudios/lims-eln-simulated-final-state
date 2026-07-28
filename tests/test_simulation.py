from __future__ import annotations

import json
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from lims_eln_sim.assurance import AuthorizationBoundary, Principal, authorize, redact_trace
from lims_eln_sim.simulation import run
from lims_eln_sim.vendors import IdempotencyConflict, SapioEmulator


class SimulationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.fixture = json.loads((ROOT / "fixtures" / "golden-specimen.json").read_text())

    def test_complete_forecast_uses_simulated_evidence(self) -> None:
        result = run(self.fixture)
        self.assertEqual(result["evidence_mode"], "simulated")
        self.assertTrue(result["accountable_observation_required"])
        self.assertEqual(result["result"]["specimen"]["status"], "released")
        self.assertEqual(len(result["receipts"]), 4)
        self.assertTrue(all(item["evidence_mode"] == "simulated" for item in result["receipts"]))

    def test_vendor_replay_is_idempotent_and_changed_content_is_explicit(self) -> None:
        vendor = SapioEmulator()
        first = vendor.write("request-1", "SPM-SYN-1", {"revision": 1})
        replay = vendor.write("request-1", "SPM-SYN-1", {"revision": 1})
        self.assertEqual(first, replay)
        with self.assertRaises(IdempotencyConflict):
            vendor.write("request-1", "SPM-SYN-1", {"revision": 2})

    def test_tenant_boundary_provides_governed_path(self) -> None:
        principal = Principal("scientist-1", "tenant-a", ("reviewer",))
        with self.assertRaisesRegex(AuthorizationBoundary, "governed transfer workflow"):
            authorize(principal, "tenant-b", "reviewer")

    def test_trace_replaces_protected_value_with_digest(self) -> None:
        trace = redact_trace({"subject_id": "SYN-PERSON-1", "outcome": "released"})
        self.assertEqual(trace["subject_id"]["classification"], "protected")
        self.assertTrue(trace["subject_id"]["digest"].startswith("sha256:"))
        self.assertEqual(trace["outcome"], "released")

    def test_restore_and_exit_preserve_reconstructable_state(self) -> None:
        result = run(self.fixture)["result"]
        self.assertTrue(result["migration"]["semantic_parity"])
        self.assertTrue(result["restore"]["clean_environment"])
        self.assertTrue(result["data_exit"]["reconstructable"])


if __name__ == "__main__":
    unittest.main()

