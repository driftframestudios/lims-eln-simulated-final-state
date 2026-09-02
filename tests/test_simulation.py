from __future__ import annotations

from copy import deepcopy
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from hashlib import sha256
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from lims_eln_sim.assurance import AuthorizationBoundary, Principal, authorize, redact_trace
from lims_eln_sim import artifact_boundary
from lims_eln_sim import receipt_checks
from lims_eln_sim.artifact_boundary import (
    ArtifactBoundaryError,
    verify_reproducible_artifacts,
)
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
from lims_eln_sim.contract_v1 import (
    GOLDEN_SPECIMEN_SCENARIO_DIGEST,
    canonical_digest as contract_digest,
)
from lims_eln_sim.database_oracle import (
    DatabaseOracleError,
    validate_database_oracle,
)
from lims_eln_sim.domain import DomainRuleError, Specimen, digest, parse_instant
from lims_eln_sim.migration import MigrationHarness, validate_representative_corpus
from lims_eln_sim.open_receipts import ReceiptCriteriaError, close_open_receipts
from lims_eln_sim.safety import (
    SyntheticBoundary,
    synthetic_redaction_key,
)
from lims_eln_sim.simulation import closure_bundle, run, write_bundle
from lims_eln_sim.receipt_checks import verify_family
from lims_eln_sim.vendors import IdempotencyConflict, SapioEmulator


class SimulationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.fixture = json.loads((ROOT / "fixtures" / "golden-specimen.json").read_text())
        cls.migration_corpus = json.loads(
            (ROOT / "fixtures" / "representative-migration-corpus.json").read_text()
        )
        cls.intended_use_profile = json.loads(
            (
                ROOT
                / "specification"
                / "intended-use-and-applicability-profile.json"
            ).read_text()
        )
        cls.database_oracle = json.loads(
            (
                ROOT
                / "database"
                / "final-state-database-oracle-v1.json"
            ).read_text()
        )
        cls.redaction_key = synthetic_redaction_key(cls.fixture["redaction_key_id"])

    def simulate(self, fixture: dict | None = None) -> dict:
        return run(
            fixture or self.fixture,
            intended_use_profile=self.intended_use_profile,
            migration_corpus=self.migration_corpus,
            database_oracle=self.database_oracle,
            redaction_key=self.redaction_key,
        )

    def test_complete_forecast_uses_simulated_evidence(self) -> None:
        result = self.simulate()
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

    def test_isolated_runs_emit_the_same_strict_json_artifacts(self) -> None:
        with (
            tempfile.TemporaryDirectory(prefix="simulation-first-") as first,
            tempfile.TemporaryDirectory(prefix="simulation-replay-") as replay,
        ):
            first_path = Path(first)
            replay_path = Path(replay)
            write_bundle(self.simulate(), first_path)
            write_bundle(self.simulate(), replay_path)

            inventory = verify_reproducible_artifacts(first_path, replay_path)

            self.assertEqual(
                inventory["observation-envelope.json"],
                "sha256:"
                + sha256(
                    (first_path / "observation-envelope.json").read_bytes()
                ).hexdigest(),
            )

    def test_artifact_replay_detects_strict_json_and_byte_drift(self) -> None:
        with (
            tempfile.TemporaryDirectory(prefix="simulation-first-") as first,
            tempfile.TemporaryDirectory(prefix="simulation-replay-") as replay,
        ):
            first_path = Path(first)
            replay_path = Path(replay)
            write_bundle(self.simulate(), first_path)
            write_bundle(self.simulate(), replay_path)

            replay_result = replay_path / "result.json"
            replay_result.write_bytes(replay_result.read_bytes() + b"\n")
            with self.assertRaisesRegex(ArtifactBoundaryError, "byte drift"):
                verify_reproducible_artifacts(first_path, replay_path)

            write_bundle(self.simulate(), replay_path)
            changed_observation = json.loads(
                (first_path / "observation-envelope.json").read_text()
            )
            changed_observation["result"]["projection"]["lifecycle"][
                "state"
            ] = "changed"
            (first_path / "observation-envelope.json").write_text(
                json.dumps(changed_observation, sort_keys=True) + "\n",
                encoding="utf-8",
            )
            with self.assertRaisesRegex(
                ArtifactBoundaryError,
                "projections carried by result.json",
            ):
                verify_reproducible_artifacts(first_path, replay_path)

            write_bundle(self.simulate(), first_path)
            (replay_path / "result.json").write_text(
                '{"simulation_id":"one","simulation_id":"two"}\n',
                encoding="utf-8",
            )
            with self.assertRaisesRegex(ArtifactBoundaryError, "strict JSON"):
                verify_reproducible_artifacts(first_path, replay_path)

            write_bundle(self.simulate(), replay_path)
            replay_result = replay_path / "result.json"
            replay_result.unlink()
            replay_result.symlink_to(first_path / "result.json")
            with self.assertRaisesRegex(
                ArtifactBoundaryError,
                "regular output file",
            ):
                verify_reproducible_artifacts(first_path, replay_path)

    def test_artifact_boundary_rejects_exponent_overflow_twins(self) -> None:
        for numeric_value in ("1e400", "-1e400"):
            with (
                self.subTest(numeric_value=numeric_value),
                tempfile.TemporaryDirectory(prefix="simulation-first-") as first,
                tempfile.TemporaryDirectory(prefix="simulation-replay-") as replay,
            ):
                first_path = Path(first)
                replay_path = Path(replay)
                write_bundle(self.simulate(), first_path)
                write_bundle(self.simulate(), replay_path)
                (replay_path / "result.json").write_text(
                    '{"value":' + numeric_value + "}\n",
                    encoding="utf-8",
                )
                with self.assertRaisesRegex(
                    ArtifactBoundaryError,
                    "finite representation",
                ):
                    verify_reproducible_artifacts(first_path, replay_path)

    def test_artifact_boundary_requires_no_follow_platform_support(self) -> None:
        with (
            tempfile.TemporaryDirectory(prefix="simulation-first-") as first,
            tempfile.TemporaryDirectory(prefix="simulation-replay-") as replay,
        ):
            first_path = Path(first)
            replay_path = Path(replay)
            write_bundle(self.simulate(), first_path)
            write_bundle(self.simulate(), replay_path)
            with (
                mock.patch.object(
                    artifact_boundary.os,
                    "O_NOFOLLOW",
                    None,
                    create=True,
                ),
                self.assertRaisesRegex(
                    ArtifactBoundaryError,
                    "platform support for fail-closed final-path no-follow opening",
                ),
            ):
                verify_reproducible_artifacts(first_path, replay_path)

    def test_receipt_family_checker_uses_strict_repository_json_ingress(
        self,
    ) -> None:
        cases = (
            (
                "fixtures/golden-specimen.json",
                '{"fixture_class":"synthetic","fixture_class":"synthetic"}',
                "single definition",
            ),
            (
                "fixtures/representative-migration-corpus.json",
                '{"fixture_class":"representative_synthetic","value":1e400}',
                "finite representation",
            ),
            (
                "specification/intended-use-and-applicability-profile.json",
                '{"profile_version":"1.0.0","value":-1e400}',
                "finite representation",
            ),
        )
        source_paths = (
            "fixtures/golden-specimen.json",
            "fixtures/representative-migration-corpus.json",
            "specification/intended-use-and-applicability-profile.json",
        )
        for relative, content, message in cases:
            with (
                self.subTest(relative=relative),
                tempfile.TemporaryDirectory(prefix="receipt-input-") as directory,
            ):
                input_root = Path(directory)
                for source_relative in source_paths:
                    target = input_root / source_relative
                    target.parent.mkdir(parents=True, exist_ok=True)
                    target.write_bytes((ROOT / source_relative).read_bytes())
                (input_root / relative).write_text(content, encoding="utf-8")
                with (
                    mock.patch.object(receipt_checks, "ROOT", input_root),
                    self.assertRaisesRegex(ValueError, message),
                ):
                    verify_family("configured_vendor_environments")

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
        result = self.simulate()
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
        result = self.simulate()
        for family in {
            item["receipt_family"] for item in result["receipts"]
        }:
            with self.subTest(family=family):
                verified = verify_family(family)
                self.assertEqual(verified["outcome"], "passed")

    def test_receipt_closure_fails_when_independent_criterion_fails(self) -> None:
        core = deepcopy(self.simulate()["result"])
        core["telemetry"]["vendor_projection_readback"]["ratio"] = 0.5
        with self.assertRaisesRegex(
            ReceiptCriteriaError,
            "vendor_readback_sli",
        ):
            close_open_receipts(core, core["bounded_caller"])

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
        result = self.simulate()["result"]
        self.assertEqual(result["migration"]["source_count"], 4)
        self.assertEqual(result["migration_corpus"]["record_count"], 4)
        self.assertEqual(result["migration_corpus"]["artifact_count"], 3)
        self.assertTrue(result["migration"]["semantic_parity"])
        self.assertTrue(result["restore"]["clean_environment"])
        self.assertTrue(result["restore"]["readback_parity"])
        self.assertTrue(result["data_exit"]["reconstructable"])
        self.assertNotIn("independent_readback", result["restore"])
        self.assertNotIn("records", result["data_exit"])

    def test_representative_corpus_rejects_duplicate_identity(self) -> None:
        corpus = deepcopy(self.migration_corpus)
        corpus["records"][1]["specimen_id"] = corpus["records"][0]["specimen_id"]
        with self.assertRaisesRegex(ValueError, "unique specimen"):
            validate_representative_corpus(corpus)

    def test_representative_corpus_requires_exact_integer_and_digest_primitives(
        self,
    ) -> None:
        boolean_revision = deepcopy(self.migration_corpus)
        boolean_revision["records"][0]["revision"] = True
        with self.assertRaisesRegex(ValueError, "positive integer"):
            validate_representative_corpus(boolean_revision)

        boolean_size = deepcopy(self.migration_corpus)
        boolean_size["artifacts"][0]["size_bytes"] = True
        with self.assertRaisesRegex(ValueError, "positive integer"):
            validate_representative_corpus(boolean_size)

        boolean_profile_size = deepcopy(self.migration_corpus)
        boolean_profile_size["profile"]["artifact_sizes_bytes"][0] = True
        with self.assertRaisesRegex(ValueError, "positive integers"):
            validate_representative_corpus(boolean_profile_size)

        malformed_digest = deepcopy(self.migration_corpus)
        malformed_digest["records"][0]["artifact_digest"] = "sha256:short"
        with self.assertRaisesRegex(ValueError, "canonical digest"):
            validate_representative_corpus(malformed_digest)

    def test_representative_corpus_requires_contiguous_audit_revision_lineage(
        self,
    ) -> None:
        sequence_drift = deepcopy(self.migration_corpus)
        sequence_drift["records"][0]["audit"][0]["sequence"] = 2
        with self.assertRaisesRegex(ValueError, "contiguous ordered"):
            validate_representative_corpus(sequence_drift)

        revision_drift = deepcopy(self.migration_corpus)
        revision_drift["records"][0]["revision"] += 1
        with self.assertRaisesRegex(ValueError, "complete audit lineage"):
            validate_representative_corpus(revision_drift)

    def test_migration_readiness_distinguishes_boolean_from_integer_revision(
        self,
    ) -> None:
        records = deepcopy(self.migration_corpus["records"])
        records[0]["revision"] = True
        unused_target, report = MigrationHarness().migrate(records)
        self.assertFalse(report.rollback_ready)

        records = deepcopy(self.migration_corpus["records"])
        records[0]["audit"][0]["sequence"] = 2
        unused_target, report = MigrationHarness().migrate(records)
        self.assertFalse(report.rollback_ready)

    def test_runtime_cache_policy_distinguishes_boolean_from_integer(self) -> None:
        runtime_reference = deepcopy(self.fixture["runtime_configuration"])
        runtime_reference["cache_ttl_seconds"] = True
        with self.assertRaisesRegex(ConfigurationBoundary, "bounded 30-900"):
            AwsRuntimeReference.from_dict(runtime_reference)

    def test_domain_uses_aware_instants_and_returns_detached_json_views(self) -> None:
        specimen = Specimen("SPM-SYN-TIME", "TENANT-SYN-001", "source-sim")
        specimen.result = {"measurements": [{"value": "1.250000"}]}
        specimen.transition(
            "accessioned",
            "simulated-operator",
            {"source": "selected-future"},
            "2028-06-30T10:00:00-04:00",
        )

        self.assertIsInstance(specimen.audit[0].occurred_at, datetime)
        self.assertEqual(
            parse_instant("2028-06-30T10:00:00-04:00"),
            datetime(2028, 6, 30, 14, 0, tzinfo=timezone.utc),
        )
        view = specimen.view()
        self.assertEqual(view["audit"][0]["occurred_at"], "2028-06-30T14:00:00.000Z")
        view["result"]["measurements"][0]["value"] = "changed-by-consumer"
        self.assertEqual(specimen.result["measurements"][0]["value"], "1.250000")
        with self.assertRaisesRegex(ValueError, "explicit timezone"):
            parse_instant("2028-06-30T14:00:00")

    def test_custody_transition_requires_location_before_state_changes(self) -> None:
        specimen = Specimen("SPM-SYN-CUSTODY", "TENANT-SYN-001", "source-sim")
        specimen.transition(
            "accessioned",
            "simulated-operator",
            {"source": "selected-future"},
            "2028-06-30T14:00:00Z",
        )

        with self.assertRaisesRegex(DomainRuleError, "concrete location"):
            specimen.transition(
                "in_custody",
                "simulated-operator",
                {},
                "2028-06-30T14:00:01Z",
            )

        self.assertEqual(specimen.status, "accessioned")
        self.assertEqual(specimen.revision, 1)
        self.assertIsNone(specimen.custody_location)
        self.assertEqual(len(specimen.audit), 1)

    def test_shared_projection_rejects_executed_custody_drift(self) -> None:
        original_transition = Specimen.transition

        def transition_with_drift(
            specimen: Specimen,
            target: str,
            actor: str,
            detail: dict,
            occurred_at: str | datetime,
        ) -> None:
            original_transition(specimen, target, actor, detail, occurred_at)
            if target == "in_custody":
                specimen.custody_location = "SYN-LAB-A/DRIFTED"

        with mock.patch.object(Specimen, "transition", new=transition_with_drift):
            with self.assertRaisesRegex(ValueError, "custody_location"):
                self.simulate()

    def test_database_oracle_binds_contract_manifest_and_release_receipts(self) -> None:
        coordinates = validate_database_oracle(self.database_oracle)
        role = json.loads((ROOT / "release" / "repository-role.json").read_text())
        self.assertEqual(
            self.database_oracle["migration_manifest"]["tool"],
            {
                "name": "Flyway Community",
                "version": "13.0.0",
                "implementation_digest": (
                    "sha256:f3c8433401abf859ef9022584c8e6111"
                    "684363ec490f737e749e9a4705ea32d0"
                ),
            },
        )
        self.assertEqual(
            role["database_oracle"]["release_coordinates"],
            coordinates.as_dict(),
        )
        self.assertEqual(
            role["database_oracle"]["canonical_json_digest"],
            contract_digest(self.database_oracle),
        )

    def test_shared_projection_is_scenario_derived_and_oracle_traceable(self) -> None:
        result = self.simulate()
        observation = result["observation"]
        projection = observation["result"]["projection"]
        scenario = json.loads(
            (
                ROOT
                / "src"
                / "lims_eln_sim"
                / "contract_resources"
                / "golden-specimen.v1.json"
            ).read_text()
        )
        coordinates = validate_database_oracle(self.database_oracle)

        self.assertEqual(observation["evidence_mode"], "simulated")
        self.assertEqual(observation["scenario_id"], scenario["scenario_id"])
        self.assertEqual(
            observation["scenario_version"], scenario["scenario_version"]
        )
        self.assertEqual(
            observation["scenario_digest"], GOLDEN_SPECIMEN_SCENARIO_DIGEST
        )
        self.assertEqual(
            projection,
            {
                "projection_id": "urn:driftframe:lims-eln:golden-specimen-result",
                "projection_version": "1.0.0",
                "comparison_compatibility": "exact-version",
                "tenant_id": scenario["specimen"]["tenant_id"],
                "specimen_id": scenario["specimen"]["specimen_id"],
                "lifecycle": {
                    "state": scenario["expected_state"]["lifecycle_state"],
                    "aggregate_version": scenario["expected_state"][
                        "aggregate_version"
                    ],
                },
                "custody": {
                    "current_location": scenario["expected_state"][
                        "custody_location"
                    ],
                },
                "measurement": scenario["expected_state"]["result"],
                "review_resolution": {
                    "review_id": scenario["commands"][-2]["payload"]["review_id"],
                    "decision": "accepted",
                    "resolved_at": scenario["commands"][-1]["occurred_at"],
                },
                "release": {
                    "approval_receipt_id": scenario["commands"][-1]["payload"][
                        "approval_receipt_id"
                    ],
                    "released_at": scenario["commands"][-1]["occurred_at"],
                },
            },
        )
        self.assertEqual(
            contract_digest(projection),
            "sha256:cead042eaf3ca8f72b9c30c41d9acb0bd9255027448f3b28e3451305bed1aef1",
        )
        self.assertEqual(
            observation["result"]["producer_detail"]["database_oracle"],
            {
                "oracle_id": self.database_oracle["oracle_id"],
                "oracle_version": self.database_oracle["oracle_version"],
                "canonical_json_digest": contract_digest(self.database_oracle),
                "release_coordinates": coordinates.as_dict(),
            },
        )
        self.assertEqual(
            observation["source"]["configuration_digest"],
            contract_digest(
                observation["result"]["producer_detail"]["configuration"]
            ),
        )
        self.assertEqual(
            observation["provenance"]["raw_artifact_digest"],
            contract_digest(observation["result"]),
        )
        changed_local_detail = deepcopy(observation["result"])
        changed_local_detail["producer_detail"]["simulation"]["execution"][
            "trace_id"
        ] = "sim-trace-local-iteration"
        self.assertEqual(
            contract_digest(changed_local_detail["projection"]),
            contract_digest(projection),
        )
        self.assertNotEqual(
            contract_digest(changed_local_detail),
            observation["provenance"]["raw_artifact_digest"],
        )

    def test_simulation_rejects_database_oracle_coordinate_drift(self) -> None:
        drifted = deepcopy(self.database_oracle)
        drifted["coordinates"]["release_receipt_digest"] = "sha256:" + "f" * 64
        with self.assertRaisesRegex(DatabaseOracleError, "canonical nested"):
            run(
                self.fixture,
                intended_use_profile=self.intended_use_profile,
                migration_corpus=self.migration_corpus,
                database_oracle=drifted,
                redaction_key=self.redaction_key,
            )

    def test_database_oracle_enforces_native_primitives_and_exact_json_types(
        self,
    ) -> None:
        mutations = []

        boolean_sequence = deepcopy(self.database_oracle)
        boolean_sequence["migration_manifest"]["phases"][0]["sequence"] = True
        mutations.append((boolean_sequence, "positive integer"))

        text_instant = deepcopy(self.database_oracle)
        text_instant["data_contract"]["entities"][0]["fields"][5][
            "physical_type"
        ] = "text"
        mutations.append((text_instant, "uses timestamptz"))

        numeric_acceptance_flag = deepcopy(self.database_oracle)
        numeric_acceptance_flag["actual_acceptance_required"] = 1
        mutations.append((numeric_acceptance_flag, "actual_acceptance_required"))

        noncanonical_time = deepcopy(self.database_oracle)
        noncanonical_time["migration_receipt"]["performed_at"] = (
            "2028-06-30T14:25:00Z"
        )
        mutations.append((noncanonical_time, "millisecond canonical UTC"))

        missing_acceptance = deepcopy(self.database_oracle)
        missing_acceptance["release_receipt"]["acceptance_bindings"].pop()
        mutations.append((missing_acceptance, "distinct Scientific"))

        for candidate, message in mutations:
            with self.subTest(message=message), self.assertRaisesRegex(
                DatabaseOracleError, message
            ):
                validate_database_oracle(candidate)

    def test_database_oracle_detects_nested_digest_drift(self) -> None:
        drifted = deepcopy(self.database_oracle)
        drifted["coordinates"]["release_receipt_digest"] = (
            "sha256:ffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffff"
        )
        with self.assertRaisesRegex(DatabaseOracleError, "canonical nested"):
            validate_database_oracle(drifted)

    def test_schema_valid_utc_offset_produces_canonical_event_times(self) -> None:
        fixture = deepcopy(self.fixture)
        fixture["clock"] = "2026-08-17T14:30:00+00:00"
        result = self.simulate(fixture)
        event_times = [
            item["occurred_at"] for item in result["result"]["specimen"]["audit"]
        ]
        self.assertTrue(all(value.endswith("Z") for value in event_times))
        self.assertTrue(all("+00:" not in value for value in event_times))

    def test_failure_twins_surface_semantic_and_restore_variance(self) -> None:
        result = self.simulate()["result"]
        self.assertFalse(result["failure_twins"]["migration"]["semantic_parity"])
        self.assertTrue(result["failure_twins"]["migration"]["mismatch_paths"])
        self.assertFalse(result["failure_twins"]["restore"]["readback_parity"])
        self.assertFalse(result["failure_twins"]["restore"]["qualification_ready"])

    def test_fixture_boundary_requires_generated_identity_and_content(self) -> None:
        fixture = deepcopy(self.fixture)
        fixture["specimen_id"] = "EXTERNAL-RECORD-1"
        with self.assertRaisesRegex(SyntheticBoundary, "generated SPM-SYN"):
            self.simulate(fixture)

        fixture = deepcopy(self.fixture)
        fixture["result"]["api_key"] = "SYNTHETIC-CREDENTIAL-SHAPE"
        with self.assertRaisesRegex(SyntheticBoundary, "protected content"):
            self.simulate(fixture)

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
            ('{"value":1e400}', "finite representation"),
            ('{"value":-1e400}', "finite representation"),
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
        result = self.simulate()
        closure_digest = digest(result["governance_closure"])
        self.assertEqual(__version__, "0.3.1")
        self.assertEqual(manifest["repository_release"], __version__)
        self.assertEqual(manifest["repository_role"], "simulated_final_state")
        self.assertEqual(manifest["contract_bindings"]["governance_schema"], "2.1.0")
        self.assertEqual(
            manifest["reference_result_digest"],
            result["content_digest"],
        )
        self.assertEqual(manifest["reference_closure_digest"], closure_digest)
        retained_bundle = json.loads(
            (
                ROOT
                / manifest["canonical_closure_bundle"]["path"]
            ).read_text()
        )
        self.assertEqual(
            manifest["canonical_closure_bundle"]["canonical_json_digest"],
            digest(retained_bundle),
        )
        retained_path = (
            ROOT
            / manifest["canonical_closure_bundle"]["path"]
        )
        self.assertEqual(
            manifest["canonical_closure_bundle"]["file_sha256"],
            f"sha256:{sha256(retained_path.read_bytes()).hexdigest()}",
        )
        self.assertEqual(
            manifest["aggregate_closure_artifact_digest"],
            retained_bundle["governance_closure"]["aggregate_artifacts"][0][
                "digest"
            ],
        )
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

    def test_release_closure_bundle_is_reproduced_from_declared_inputs(self) -> None:
        retained = json.loads(
            (
                ROOT
                / "release"
                / "future-reality-2028-06-30-v1.json"
            ).read_text()
        )
        generated = closure_bundle(self.simulate())
        self.assertEqual(retained, generated)
        self.assertEqual(retained["bundle_version"], "2.0.1")
        self.assertEqual(
            retained["source_result_digest"],
            self.simulate()["content_digest"],
        )

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
        manifest = json.loads(
            (ROOT / "release" / "repository-role.json").read_text()
        )
        result = self.simulate()
        expected_ids = set(
            result["governance_closure"]["future_reality"]["assumption_ids"]
        )
        self.assertEqual(
            expected_ids,
            {item["assumption_id"] for item in assumptions["assumptions"]},
        )
        self.assertEqual(
            manifest["assumptions_ledger"],
            {
                "path": "ledgers/assumptions.json",
                "canonical_json_digest": digest(assumptions),
            },
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
        self.assertEqual(lock["constellation_version"], "0.3.1")
        self.assertEqual(
            lock["specification"],
            {
                "release": None,
                "package_version": "0.3.1",
                "commit": "4d06eeb7f96910311fbcb7f51547c978b6a07290",
                "digest": "git-tree-sha1:887e2c12a699105994097e4e9094270453de16ba",
                "source_identity_digest": (
                    "sha256:e4d7ef6aa1036b69395e9de3ab0064297dc80e5f697ab60de699a355e45f7674"
                ),
                "acceptance_lineage_commit": (
                    "c155551f5ac2c203fd9d08190d7020bba0cf71f8"
                ),
                "coordinate_status": "accepted_package_source",
                "complete_specification_release": "pending",
            },
        )
        self.assertEqual(lock["simulation"]["release"], "forecast-2028-FR-v1")
        self.assertEqual(
            lock["simulation"]["canonical_closure_digest"],
            digest(result["governance_closure"]),
        )
        self.assertEqual(lock["comparison"]["receipt_schema"], "2.0.1")
        self.assertEqual(
            lock["implementation"],
            {
                "release": "v0.3.1",
                "tag_object_oid": "8b1013ff6a116b64e5d31c2870b574f641ee88f6",
                "commit": "44a4b8e67ff2e6af232b12daf3692bee8e8f3a3a",
                "digest": "git-tree-sha1:cc1bb335c0cdd1a37d1b6554480b3afdb9c9f360",
                "archive_digest": (
                    "sha256:00da1be41bdf23a21124d600f3788464bfd8f590c819f6a9c74b98671edb2174"
                ),
                "observation_carrier_commit": (
                    "7e17bb9840f2936d7c83d63f36bfdb08b768ecb5"
                ),
                "coordinate_status": "release_observed",
                "source_binding_status": "accepted_program_coordinate",
            },
        )
        self.assertEqual(
            lock["governance"],
            {
                "release": "governance-v2.1.0",
                "profile": "Control Plane Profile 0.3.0",
                "schema_version": "2.1.0",
                "tag_object_oid": "1c77396e44b71719ccab138fecd02e525089e39d",
                "commit": "8469c2a6b2c7f4445523cee262b961ffe3d2523b",
                "digest": "git-tree-sha1:aed5d57120e15ceabe77d7bba700a43097200b19",
                "archive_digest": (
                    "sha256:469ae49fca7d5ad6e1766080b3c39d76c46a840366b217f3839b9d34f2e77d32"
                ),
                "observation_carrier_commit": (
                    "43549173f850607ff73382fabb3d48906ff92f62"
                ),
                "coordinate_status": "release_observed",
            },
        )
        self.assertEqual(
            lock["simulation"]["coordinate_status"],
            "pending_release_commit",
        )


if __name__ == "__main__":
    unittest.main()
