from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from lims_eln_sim.assurance import AuthorizationBoundary, Principal, authorize, redact_trace
from lims_eln_sim import __version__
from lims_eln_sim.cli import load_json
from lims_eln_sim.configuration import (
    AwsRuntimeReference,
    ConfigurationBoundary,
    SyntheticAwsProvider,
    resolve_runtime_configuration,
)
from lims_eln_sim.safety import (
    SyntheticBoundary,
    synthetic_redaction_key,
)
from lims_eln_sim.simulation import run
from lims_eln_sim.vendors import IdempotencyConflict, SapioEmulator


class SimulationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.fixture = json.loads((ROOT / "fixtures" / "golden-specimen.json").read_text())
        cls.redaction_key = synthetic_redaction_key(cls.fixture["redaction_key_id"])

    def test_complete_forecast_uses_simulated_evidence(self) -> None:
        result = run(self.fixture, redaction_key=self.redaction_key)
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

    def test_trace_replaces_protected_value_with_keyed_pseudonym(self) -> None:
        trace = redact_trace(
            {
                "Subject_ID": "SYN-PERSON-1",
                "nested": {"Email": "generated@example.invalid"},
                "outcome": "released",
            },
            key=self.redaction_key,
        )
        self.assertEqual(trace["Subject_ID"]["classification"], "protected")
        self.assertTrue(trace["Subject_ID"]["pseudonym"].startswith("hmac-sha256:"))
        self.assertEqual(trace["nested"]["Email"]["classification"], "protected")
        self.assertEqual(trace["outcome"], "released")

    def test_restore_and_exit_preserve_reconstructable_state(self) -> None:
        result = run(self.fixture, redaction_key=self.redaction_key)["result"]
        self.assertTrue(result["migration"]["semantic_parity"])
        self.assertTrue(result["restore"]["clean_environment"])
        self.assertTrue(result["restore"]["readback_parity"])
        self.assertTrue(result["data_exit"]["reconstructable"])
        self.assertNotIn("independent_readback", result["restore"])
        self.assertNotIn("records", result["data_exit"])

    def test_failure_twins_surface_semantic_and_restore_variance(self) -> None:
        result = run(self.fixture, redaction_key=self.redaction_key)["result"]
        self.assertFalse(result["failure_twins"]["migration"]["semantic_parity"])
        self.assertTrue(result["failure_twins"]["migration"]["mismatch_paths"])
        self.assertFalse(result["failure_twins"]["restore"]["readback_parity"])
        self.assertFalse(result["failure_twins"]["restore"]["qualification_ready"])

    def test_fixture_boundary_requires_generated_identity_and_content(self) -> None:
        fixture = deepcopy(self.fixture)
        fixture["specimen_id"] = "EXTERNAL-RECORD-1"
        with self.assertRaisesRegex(SyntheticBoundary, "generated SPM-SYN"):
            run(fixture, redaction_key=self.redaction_key)

        fixture = deepcopy(self.fixture)
        fixture["result"]["api_key"] = "SYNTHETIC-CREDENTIAL-SHAPE"
        with self.assertRaisesRegex(SyntheticBoundary, "protected content"):
            run(fixture, redaction_key=self.redaction_key)

    def test_aws_provider_receipt_preserves_references_and_versions(self) -> None:
        reference = AwsRuntimeReference.from_dict(self.fixture["runtime_configuration"])
        resolved = resolve_runtime_configuration(reference, SyntheticAwsProvider())
        receipt = json.dumps(resolved.receipt, sort_keys=True)
        self.assertEqual(resolved.receipt["provider_contract"], "aws-ssm-and-secrets-manager")
        self.assertIn("/lims-eln/simulated/vendor/base-url", receipt)
        self.assertNotIn(next(iter(resolved.secrets.values())), receipt)
        self.assertNotIn(next(iter(resolved.parameters.values())), receipt)

        external_reference = deepcopy(self.fixture["runtime_configuration"])
        external_reference["workload_role_arn"] = (
            "arn:aws:iam::999988887777:role/live-environment-role"
        )
        with self.assertRaisesRegex(ConfigurationBoundary, "bounded AWS IAM role"):
            AwsRuntimeReference.from_dict(external_reference)

    def test_json_ingress_rejects_duplicate_and_nonfinite_values(self) -> None:
        examples = (
            ('{"fixture_class":"synthetic","fixture_class":"observed"}', "single definition"),
            ('{"value":NaN}', "finite representation"),
        )
        for content, message in examples:
            with self.subTest(message=message), tempfile.TemporaryDirectory() as directory:
                path = Path(directory) / "fixture.json"
                path.write_text(content, encoding="utf-8")
                with self.assertRaisesRegex(ValueError, message):
                    load_json(path)

    def test_repository_release_binds_role_and_contracts(self) -> None:
        manifest = json.loads((ROOT / "release" / "repository-role.json").read_text())
        self.assertEqual(__version__, "0.2.0")
        self.assertEqual(manifest["repository_release"], __version__)
        self.assertEqual(manifest["repository_role"], "simulated_final_state")
        self.assertEqual(manifest["contract_bindings"]["governance_schema"], "1.0.0")
        self.assertEqual(
            manifest["reference_result_digest"],
            run(self.fixture, redaction_key=self.redaction_key)["content_digest"],
        )
        self.assertEqual(
            manifest["historical_external_releases"][0]["external_release"],
            "forecast-2026-Q3-r1",
        )


if __name__ == "__main__":
    unittest.main()
