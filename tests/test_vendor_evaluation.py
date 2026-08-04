from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
import json
from pathlib import Path
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from lims_eln_sim.assurance import redact_trace
from lims_eln_sim.cli import load_json
from lims_eln_sim.configuration import (
    AwsRuntimeReference,
    ConfigurationBoundary,
    SyntheticAwsProvider,
    resolve_runtime_configuration,
)
from lims_eln_sim.domain import Specimen, parse_instant
from lims_eln_sim.database_reference import (
    DatabaseReferenceError,
    inspect_database_reference,
)
from lims_eln_sim.migration import MigrationHarness, validate_representative_corpus
from lims_eln_sim.safety import SyntheticBoundary, synthetic_redaction_key
from lims_eln_sim.simulation import run, write_bundle
from lims_eln_sim.vendors import IdempotencyConflict, SapioEmulator


class VendorEvaluationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.fixture = load_json(ROOT / "fixtures" / "golden-specimen.json")
        cls.migration_corpus = load_json(
            ROOT / "fixtures" / "representative-migration-corpus.json"
        )
        cls.intended_use_profile = load_json(
            ROOT
            / "specification"
            / "intended-use-and-applicability-profile.json"
        )
        cls.database_reference = load_json(
            ROOT / "database" / "vendor-evaluation-database-reference-v1.json"
        )
        cls.redaction_key = synthetic_redaction_key(cls.fixture["redaction_key_id"])

    def evaluate(self, fixture: dict | None = None) -> dict:
        return run(
            fixture or self.fixture,
            intended_use_profile=self.intended_use_profile,
            migration_corpus=self.migration_corpus,
            database_reference=self.database_reference,
            redaction_key=self.redaction_key,
        )

    def test_reference_is_advisory_vendor_evidence(self) -> None:
        evaluation = self.evaluate()
        self.assertEqual(evaluation["reference_kind"], "synthetic_vendor_evaluation")
        self.assertEqual(evaluation["runtime_effect"], "none")
        self.assertEqual(
            evaluation["summary"]["vendors"],
            ["sapio", "benchling", "labkey"],
        )
        self.assertTrue(evaluation["summary"]["vendor_readback_converged"])
        self.assertEqual(
            evaluation["result"]["database_reference"]["migration_tool"],
            "Flyway Community",
        )

    def test_vendor_projection_and_event_readback_converge(self) -> None:
        result = self.evaluate()["result"]
        specimen_id = result["specimen"]["specimen_id"]
        self.assertEqual(result["vendors"]["sapio"]["external_id"], specimen_id)
        self.assertEqual(
            result["vendors"]["benchling"]["authoritative_readback"][
                "external_id"
            ],
            specimen_id,
        )
        self.assertEqual(
            result["vendors"]["labkey"]["record"]["external_id"],
            specimen_id,
        )
        self.assertEqual(result["event_delivery"]["pattern"], "thin_transactional_outbox")
        self.assertEqual(result["event_delivery"]["outcome"], "readback_converged")

    def test_vendor_idempotency_distinguishes_replay_from_changed_content(self) -> None:
        vendor = SapioEmulator()
        first = vendor.write("request-1", "SPM-SYN-1", {"revision": 1})
        replay = vendor.write("request-1", "SPM-SYN-1", {"revision": 1})
        self.assertEqual(first, replay)
        with self.assertRaises(IdempotencyConflict):
            vendor.write("request-1", "SPM-SYN-1", {"revision": 2})

    def test_migration_and_restore_comparison_preserve_semantics(self) -> None:
        result = self.evaluate()["result"]
        self.assertEqual(result["migration_corpus"]["record_count"], 4)
        self.assertEqual(result["migration_corpus"]["artifact_count"], 3)
        self.assertTrue(result["migration"]["semantic_parity"])
        self.assertTrue(result["restore"]["readback_parity"])
        self.assertFalse(result["failure_twins"]["migration"]["semantic_parity"])
        self.assertFalse(result["failure_twins"]["restore"]["readback_parity"])

    def test_database_reference_compares_material_primitives(self) -> None:
        summary = inspect_database_reference(self.database_reference)
        self.assertEqual(summary["engine"], "postgresql")
        self.assertEqual(summary["scientific_quantity_type"], "numeric(38,12)")
        text_timestamp = deepcopy(self.database_reference)
        specimen = next(
            item
            for item in text_timestamp["data_contract"]["entities"]
            if item["entity_id"] == "ENTITY-SPECIMEN"
        )
        updated_at = next(
            item for item in specimen["fields"] if item["field_id"] == "UPDATED-AT"
        )
        updated_at["physical_type"] = "text"
        with self.assertRaisesRegex(DatabaseReferenceError, "timestamptz"):
            inspect_database_reference(text_timestamp)

    def test_representative_corpus_rejects_type_and_lineage_drift(self) -> None:
        boolean_revision = deepcopy(self.migration_corpus)
        boolean_revision["records"][0]["revision"] = True
        with self.assertRaisesRegex(ValueError, "positive integer"):
            validate_representative_corpus(boolean_revision)

        sequence_drift = deepcopy(self.migration_corpus)
        sequence_drift["records"][0]["audit"][0]["sequence"] = 2
        with self.assertRaisesRegex(ValueError, "contiguous ordered"):
            validate_representative_corpus(sequence_drift)

    def test_migration_readiness_distinguishes_boolean_from_integer(self) -> None:
        records = deepcopy(self.migration_corpus["records"])
        records[0]["revision"] = True
        unused_target, report = MigrationHarness().migrate(records)
        self.assertFalse(report.rollback_ready)

    def test_trace_redaction_preserves_shape_and_replaces_values(self) -> None:
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

    def test_fixture_boundary_requires_synthetic_identity_and_scientific_units(
        self,
    ) -> None:
        external_identity = deepcopy(self.fixture)
        external_identity["specimen_id"] = "EXTERNAL-RECORD-1"
        with self.assertRaisesRegex(SyntheticBoundary, "generated SPM-SYN"):
            self.evaluate(external_identity)

        bare_unit = deepcopy(self.fixture)
        bare_unit["result"]["canonical_unit"] = "copies"
        with self.assertRaisesRegex(SyntheticBoundary, "canonical UCUM"):
            self.evaluate(bare_unit)

    def test_runtime_configuration_exposes_references_without_secret_values(self) -> None:
        reference = AwsRuntimeReference.from_dict(self.fixture["runtime_configuration"])
        resolved = resolve_runtime_configuration(reference, SyntheticAwsProvider())
        public_record = json.dumps(resolved.reference, sort_keys=True)
        self.assertIn("/lims-eln/simulated/vendor/base-url", public_record)
        self.assertNotIn(next(iter(resolved.secrets.values())), public_record)
        self.assertNotIn(next(iter(resolved.parameters.values())), public_record)

        invalid_reference = deepcopy(self.fixture["runtime_configuration"])
        invalid_reference["cache_ttl_seconds"] = True
        with self.assertRaisesRegex(ConfigurationBoundary, "bounded 30-900"):
            AwsRuntimeReference.from_dict(invalid_reference)

    def test_domain_instants_are_aware_and_views_are_detached(self) -> None:
        specimen = Specimen("SPM-SYN-TIME", "TENANT-SYN-001", "source-sim")
        specimen.result = {"measurements": [{"value": "1.250000"}]}
        specimen.transition(
            "accessioned",
            "simulated-operator",
            {"source": "vendor-evaluation"},
            "2028-06-30T10:00:00-04:00",
        )
        self.assertEqual(
            parse_instant("2028-06-30T10:00:00-04:00"),
            datetime(2028, 6, 30, 14, 0, tzinfo=timezone.utc),
        )
        view = specimen.view()
        view["result"]["measurements"][0]["value"] = "changed-by-consumer"
        self.assertEqual(specimen.result["measurements"][0]["value"], "1.250000")
        with self.assertRaisesRegex(ValueError, "explicit timezone"):
            parse_instant("2028-06-30T14:00:00")

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

    def test_bundle_writer_emits_one_portable_result(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory)
            write_bundle(self.evaluate(), output)
            self.assertEqual([path.name for path in output.iterdir()], ["result.json"])
            written = load_json(output / "result.json")
            self.assertEqual(written["evaluation_id"], "VENDOR-EVALUATION-001")


if __name__ == "__main__":
    unittest.main()
