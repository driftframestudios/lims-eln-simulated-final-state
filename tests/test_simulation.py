from __future__ import annotations

from copy import deepcopy
from dataclasses import replace
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from lims_eln_sim.assurance import AuthorizationBoundary, Principal, authorize, redact_trace
from lims_eln_sim.bounded_caller import (
    Approval,
    CallIntent,
    Caller,
    CallerBoundary,
    EffectClass,
    OperationContract,
    OperationRegistry,
    simulate_control_plane,
)
from lims_eln_sim import __version__
from lims_eln_sim.cli import load_json
from lims_eln_sim.configuration import (
    AwsRuntimeReference,
    ConfigurationBoundary,
    SyntheticAwsProvider,
    resolve_runtime_configuration,
)
from lims_eln_sim.domain import digest
from lims_eln_sim.safety import (
    SyntheticBoundary,
    synthetic_redaction_key,
)
from lims_eln_sim.simulation import run
from lims_eln_sim.receipt_checks import verify_family
from lims_eln_sim.vendors import IdempotencyConflict, SapioEmulator


class SimulationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.fixture = json.loads((ROOT / "fixtures" / "golden-specimen.json").read_text())
        cls.redaction_key = synthetic_redaction_key(cls.fixture["redaction_key_id"])

    def test_complete_forecast_uses_simulated_evidence(self) -> None:
        result = run(self.fixture, redaction_key=self.redaction_key)
        self.assertEqual(result["evidence_mode"], "simulated")
        self.assertFalse(result["accountable_observation_required"])
        self.assertEqual(result["assurance_stage"], "verified")
        self.assertEqual(result["result"]["specimen"]["status"], "released")
        self.assertEqual(len(result["receipts"]), 4)
        self.assertTrue(all(item["evidence_mode"] == "simulated" for item in result["receipts"]))
        self.assertTrue(result["receipt_closure_summary"]["all_closed"])
        self.assertTrue(
            all(
                item["closure_status"] == "closed_in_simulation"
                for item in result["receipts"]
            )
        )
        self.assertEqual(
            result["governance_closure"]["closure_status"],
            "closed_in_simulation",
        )
        self.assertEqual(
            result["governance_closure"]["environment_observed_closure"],
            "separate_unasserted_state",
        )
        self.assertEqual(
            result["governance_closure"]["production_authorization_effect"],
            "none",
        )

    def test_bounded_caller_control_plane_models_authority_and_replay(self) -> None:
        result = simulate_control_plane()
        self.assertTrue(result["replay_converged"])
        self.assertEqual(result["summary"]["allowed_operations"], 3)
        self.assertTrue(result["summary"]["broad_write_approval_bound"])
        self.assertEqual(
            {item["scenario"] for item in result["bounded_scenarios"]},
            {"approval_required", "cross_tenant", "unreleased_operation"},
        )

    def test_bounded_caller_replay_binds_identity_and_returns_a_fresh_snapshot(
        self,
    ) -> None:
        now = datetime(2028, 6, 30, 14, 0, tzinfo=timezone.utc)
        contract = OperationContract(
            "read_specimen_projection",
            EffectClass.READ,
            ("evidence_reader",),
            5,
            4096,
            False,
        )
        registry = OperationRegistry((contract,), clock=lambda: now)
        intent = CallIntent(
            "SIM-REPLAY-IDENTITY-001",
            contract.operation_id,
            "tenant-simulated",
            ("SPM-SYN-001",),
            {"projection": ["identity"]},
            now.isoformat(),
        )
        caller = Caller(
            "sim-evidence-reader-a",
            "tenant-simulated",
            ("evidence_reader",),
        )
        executions: list[str] = []

        first = registry.invoke(
            caller,
            intent,
            lambda unused: executions.append("executed")
            or {"records": [{"specimen_id": "SPM-SYN-001"}]},
        )
        first["outcome"]["records"][0]["specimen_id"] = "changed-by-consumer"
        replay = registry.invoke(caller, intent, lambda unused: {"unexpected": True})

        self.assertEqual(executions, ["executed"])
        self.assertEqual(
            replay["outcome"]["records"][0]["specimen_id"],
            "SPM-SYN-001",
        )
        with self.assertRaisesRegex(CallerBoundary, "different caller"):
            registry.invoke(
                Caller(
                    "sim-evidence-reader-b",
                    "tenant-simulated",
                    ("evidence_reader",),
                ),
                intent,
                lambda unused: {"unexpected": True},
            )

    def test_bounded_caller_uses_service_time_for_freshness_and_approval(
        self,
    ) -> None:
        service_time = [datetime(2028, 6, 30, 14, 6, tzinfo=timezone.utc)]
        contract = OperationContract(
            "activate_migration_wave",
            EffectClass.BROAD_WRITE,
            ("migration_operator",),
            5,
            4096,
            True,
        )
        registry = OperationRegistry(
            (contract,),
            clock=lambda: service_time[0],
            maximum_request_age=timedelta(minutes=15),
        )
        caller = Caller(
            "sim-migration-operator",
            "tenant-simulated",
            ("migration_operator",),
        )
        intent = CallIntent(
            "SIM-TIME-BOUND-001",
            contract.operation_id,
            "tenant-simulated",
            ("SPM-SYN-001",),
            {"wave_id": "wave-simulated-04"},
            "2028-06-30T14:00:00Z",
        )
        approval = Approval(
            "SIM-APPROVAL-TIME-001",
            intent.request_id,
            caller.caller_id,
            contract.operation_id,
            contract.version,
            contract.contract_digest,
            intent.tenant_id,
            intent.record_ids,
            intent.payload_digest,
            "simulated-program-owner",
            "simulated_accountable_approver",
            "2028-06-30T13:59:00Z",
            "2028-06-30T14:05:00Z",
        )

        with self.assertRaisesRegex(CallerBoundary, "approval window has elapsed"):
            registry.invoke(
                caller,
                intent,
                lambda unused: {"wave_activated": True},
                approval=approval,
            )

        service_time[0] = datetime(2028, 6, 30, 14, 3, tzinfo=timezone.utc)
        active_approval = replace(
            approval,
            approval_id="SIM-APPROVAL-TIME-002",
            expires_at="2028-06-30T14:10:00Z",
            revoked_at="2028-06-30T14:02:00Z",
        )
        with self.assertRaisesRegex(CallerBoundary, "approval was revoked"):
            registry.invoke(
                caller,
                intent,
                lambda unused: {"wave_activated": True},
                approval=active_approval,
            )

        service_time[0] = datetime(2028, 6, 30, 14, 16, tzinfo=timezone.utc)
        with self.assertRaisesRegex(CallerBoundary, "freshness window"):
            registry.invoke(
                caller,
                intent,
                lambda unused: {"wave_activated": True},
                approval=approval,
            )

    def test_all_four_receipts_close_in_one_selected_future_reality(self) -> None:
        result = run(self.fixture, redaction_key=self.redaction_key)
        receipts = result["receipts"]
        self.assertEqual(
            {item["receipt_family"] for item in receipts},
            {
                "configured_vendor_environments",
                "representative_migration_restore_rehearsals",
                "production_security_observability",
                "accountable_scientific_quality_regulatory_acceptance",
            },
        )
        self.assertEqual(
            {item["future_reality_version"] for item in receipts},
            {"future-reality-2028-06-30-v1"},
        )
        self.assertTrue(all(item["outcome"] == "passed" for item in receipts))

    def test_each_declared_receipt_check_is_executable(self) -> None:
        result = run(self.fixture, redaction_key=self.redaction_key)
        for family in {
            item["receipt_family"] for item in result["receipts"]
        }:
            with self.subTest(family=family):
                verified = verify_family(family)
                self.assertEqual(verified["outcome"], "passed")

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
        machine_node = json.loads((ROOT / "machine-node.json").read_text())
        first_receipt = json.loads((ROOT / "first-receipt.json").read_text())
        horizon = json.loads((ROOT / "COORDINATION-HORIZON.json").read_text())
        result = run(self.fixture, redaction_key=self.redaction_key)
        closure_digest = digest(result["governance_closure"])
        self.assertEqual(__version__, "0.3.0")
        self.assertEqual(manifest["repository_release"], __version__)
        self.assertEqual(manifest["repository_role"], "simulated_final_state")
        self.assertEqual(manifest["contract_bindings"]["governance_schema"], "2.0.0")
        self.assertEqual(
            manifest["reference_result_digest"],
            result["content_digest"],
        )
        self.assertEqual(manifest["reference_closure_digest"], closure_digest)
        self.assertEqual(
            machine_node["coordination_horizon_id"],
            horizon["horizon_id"],
        )
        self.assertEqual(
            first_receipt["coordination_horizon_id"],
            horizon["horizon_id"],
        )
        self.assertEqual(
            machine_node["first_receipt_contract_id"],
            first_receipt["first_receipt_id"],
        )
        self.assertIn(
            closure_digest,
            {item["digest"] for item in machine_node["contracts"]},
        )
        self.assertIn(
            closure_digest,
            {item["digest"] for item in first_receipt["contract_state"]},
        )
        self.assertEqual(
            {
                item["external_release"]
                for item in manifest["historical_external_releases"]
            },
            {"forecast-2026-Q3-r1", "forecast-2026-Q3-r2"},
        )
        self.assertEqual("settling", machine_node["lifecycle_state"])
        self.assertEqual(
            "0000000000000000000000000000000000000000",
            machine_node["current_provenance"]["commit"],
        )
        self.assertEqual(
            machine_node["open_receipts"],
            first_receipt["open_receipts"],
        )
        self.assertIn(
            "RCP-SIMULATION-PROMOTION-003",
            machine_node["open_receipts"],
        )
        self.assertEqual(
            manifest["release_coordinates"]["open_promotion_receipt_id"],
            "RCP-SIMULATION-PROMOTION-003",
        )
        self.assertEqual(
            horizon["current_item_ids"],
            ["HORIZON-SIMULATION-PROMOTION-003"],
        )
        promotion = next(
            item
            for item in horizon["work_items"]
            if item["item_id"] == "HORIZON-SIMULATION-PROMOTION-003"
        )
        self.assertEqual(promotion["state"], "settling")

    def test_forecast_ledger_is_explicit_historical_seed_lineage(self) -> None:
        ledger = json.loads((ROOT / "ledgers" / "forecasts.json").read_text())
        self.assertEqual("forecast-2026-Q3-r2", ledger["forecast_release"])
        self.assertEqual("historical_seed_calibration", ledger["ledger_role"])
        self.assertEqual("seed_input_only", ledger["current_release_effect"])
        self.assertEqual("forecast-2028-FR-v1", ledger["superseded_by"])

    def test_selected_future_assumptions_and_constellation_are_resolvable(self) -> None:
        assumptions = json.loads(
            (ROOT / "ledgers" / "assumptions.json").read_text()
        )
        result = run(self.fixture, redaction_key=self.redaction_key)
        expected_ids = set(
            result["governance_closure"]["future_reality"]["assumption_ids"]
        )
        self.assertEqual(
            expected_ids,
            {item["assumption_id"] for item in assumptions["assumptions"]},
        )
        self.assertEqual(
            assumptions["future_reality_id"],
            result["governance_closure"]["future_reality"]["future_reality_id"],
        )
        self.assertEqual(
            assumptions["future_reality_version"],
            result["future_reality_version"],
        )
        self.assertEqual(
            assumptions["historical_seed_lineage"]["classification"],
            "seed_input_only",
        )

        lock = json.loads((ROOT / "constellation.lock.json").read_text())
        self.assertEqual(lock["constellation_version"], "0.3.0")
        self.assertEqual(lock["simulation"]["release"], "forecast-2028-FR-v1")
        self.assertEqual(
            lock["simulation"]["canonical_closure_digest"],
            digest(result["governance_closure"]),
        )
        self.assertEqual(lock["comparison"]["receipt_schema"], "2.0.0")
        self.assertEqual(
            lock["simulation"]["coordinate_status"],
            "pending_release_commit",
        )


if __name__ == "__main__":
    unittest.main()
