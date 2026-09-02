from __future__ import annotations

from copy import deepcopy
from hashlib import sha256
from importlib.util import find_spec
import json
from pathlib import Path
import sys
import tomllib
import unittest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from lims_eln_sim.contract_v1 import (
    CONTRACT_DISTRIBUTION_VERSION,
    GOLDEN_SPECIMEN_RESULT_COMPATIBILITY,
    GOLDEN_SPECIMEN_RESULT_PROJECTION_ID,
    GOLDEN_SPECIMEN_RESULT_PROJECTION_VERSION,
    GOLDEN_SPECIMEN_SCENARIO_DIGEST,
    GOLDEN_SPECIMEN_SCENARIO_VERSION,
    ContractBoundaryError,
    canonical_digest,
    contract_reference,
    load_contract_binding,
    load_golden_specimen_result_projection_schema,
    load_golden_specimen_scenario,
    load_observation_schema,
    validate_golden_specimen_observation,
    validate_observation_v1,
    validate_with_shared_package,
    verify_shared_package,
)
from lims_eln_sim.safety import synthetic_redaction_key
from lims_eln_sim.simulation import run


SPECIFICATION_SOURCE = (
    ROOT.parent / "lims-eln-program-specification" / "src"
)
SPECIFICATION_DEPENDENCIES_AVAILABLE = find_spec("pydantic") is not None
INSTALLED_SPECIFICATION_AVAILABLE = find_spec("lims_eln_contracts") is not None
SPECIFICATION_BOUNDARY_AVAILABLE = (
    SPECIFICATION_DEPENDENCIES_AVAILABLE
    and (INSTALLED_SPECIFICATION_AVAILABLE or SPECIFICATION_SOURCE.is_dir())
)


class ContractV1Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.fixture = json.loads(
            (ROOT / "fixtures" / "golden-specimen.json").read_text()
        )
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

    def simulate(self, *, scenario: dict | None = None) -> dict:
        return run(
            self.fixture,
            intended_use_profile=self.intended_use_profile,
            migration_corpus=self.migration_corpus,
            database_oracle=self.database_oracle,
            redaction_key=self.redaction_key,
            scenario=scenario,
        )

    def golden_observation(self) -> dict:
        return {
            "envelope_version": "1.0.0",
            "observation_id": "SIM-OBS-GOLDEN-001",
            "evidence_mode": "simulated",
            "assurance_stage": "specified",
            "scenario_id": "SCN-GOLDEN-SPECIMEN-001",
            "scenario_version": GOLDEN_SPECIMEN_SCENARIO_VERSION,
            "scenario_digest": GOLDEN_SPECIMEN_SCENARIO_DIGEST,
            "source": {
                "environment_id": "simulated-final-state",
                "implementation_commit": "forecast-2028-FR-v1",
                "configuration_digest": "sha256:" + "1" * 64,
            },
            "result": {
                "projection": {
                    "projection_id": GOLDEN_SPECIMEN_RESULT_PROJECTION_ID,
                    "projection_version": (
                        GOLDEN_SPECIMEN_RESULT_PROJECTION_VERSION
                    ),
                    "comparison_compatibility": (
                        GOLDEN_SPECIMEN_RESULT_COMPATIBILITY
                    ),
                    "tenant_id": "TENANT-SYN-GENOMICS",
                    "specimen_id": "SPM-SYN-0001",
                    "lifecycle": {
                        "state": "released",
                        "aggregate_version": 5,
                    },
                    "custody": {
                        "current_location": "SYN-LAB-A/RECEIVING",
                    },
                    "measurement": {
                        "analyte": "synthetic-copy-number-marker",
                        "value": 2.0,
                        "unit": "copies",
                        "quality_flag": "pass",
                    },
                    "review_resolution": {
                        "review_id": "REVIEW-SYN-001",
                        "decision": "accepted",
                        "resolved_at": "2026-08-17T14:35:00Z",
                    },
                    "release": {
                        "approval_receipt_id": "APPROVAL-SYN-QUALITY-001",
                        "released_at": "2026-08-17T14:35:00Z",
                    },
                },
                "producer_detail": {
                    "execution_trace_id": "SIMULATION-TRACE-001",
                },
            },
            "provenance": {
                "raw_artifact_digest": "sha256:" + "2" * 64,
                "governed_locator": (
                    "simulation://forecast-2028-FR-v1/golden-specimen"
                ),
                "performed_by": "simulation-runner",
                "reviewed_by": "simulation-reviewer",
            },
            "approvals": [],
            "classification": {
                "data_class": "synthetic",
                "redaction_status": "generated-identities",
            },
        }

    def test_bound_snapshots_retain_released_version_and_digests(self) -> None:
        binding = load_contract_binding()
        scenario = load_golden_specimen_scenario()
        schema = load_observation_schema()
        projection_schema = load_golden_specimen_result_projection_schema()
        release = json.loads((ROOT / "release" / "repository-role.json").read_text())

        self.assertEqual(binding["contract_version"], "1.0.0")
        self.assertEqual(scenario["scenario_id"], "SCN-GOLDEN-SPECIMEN-001")
        self.assertEqual(
            schema["$id"],
            "urn:driftframe:lims-eln:observation-envelope:1.0.0",
        )
        self.assertEqual(
            projection_schema["$id"],
            "urn:driftframe:lims-eln:golden-specimen-result:1.0.0",
        )
        self.assertEqual(
            binding["resources"]["golden_result_projection_schema"],
            {
                "package_path": (
                    "resources/schemas/"
                    "golden-specimen-result-projection.v1.schema.json"
                ),
                "local_path": (
                    "contract_resources/"
                    "golden-specimen-result-projection.v1.schema.json"
                ),
                "sha256": (
                    "sha256:ab2f3200045b5521b5c9da29c6f2e03a69ced3d5e8531a3107e20d06728f2696"
                ),
                "canonical_digest": (
                    "sha256:0519835a178742d52994b1342f3fdf38281b982feca9283782d45489123871fb"
                ),
            },
        )
        self.assertEqual(
            contract_reference()[
                "golden_result_projection_schema_document_digest"
            ],
            canonical_digest(projection_schema),
        )
        self.assertEqual(
            contract_reference()["golden_scenario_document_digest"],
            canonical_digest(scenario),
        )
        self.assertEqual(
            release["external_contract_bindings"]["shared_contract_nucleus"][
                "golden_scenario_document_digest"
            ],
            contract_reference()["golden_scenario_document_digest"],
        )
        self.assertEqual(
            release["external_contract_bindings"]["shared_contract_nucleus"][
                "golden_result_projection_schema_document_digest"
            ],
            contract_reference()[
                "golden_result_projection_schema_document_digest"
            ],
        )
        self.assertEqual(
            release["contract_bindings"][
                "golden_specimen_result_projection_schema"
            ],
            "1.0.0",
        )

    def test_shared_distribution_coordinates_remain_aligned(self) -> None:
        binding = load_contract_binding()
        release = json.loads((ROOT / "release" / "repository-role.json").read_text())
        project = tomllib.loads((ROOT / "pyproject.toml").read_text())["project"]
        distribution = binding["distribution"]
        pinned_distribution = (
            f"{distribution['name']}=={CONTRACT_DISTRIBUTION_VERSION}"
        )

        self.assertEqual(distribution["version"], CONTRACT_DISTRIBUTION_VERSION)
        self.assertEqual(
            project["optional-dependencies"]["contract-conformance"],
            [pinned_distribution],
        )
        self.assertEqual(
            release["external_contract_bindings"]["shared_contract_nucleus"][
                "distribution"
            ],
            pinned_distribution,
        )

        scenario_path = (
            ROOT
            / "src"
            / "lims_eln_sim"
            / "contract_resources"
            / "golden-specimen.v1.json"
        )
        scenario_bytes = scenario_path.read_bytes()
        self.assertTrue(scenario_bytes.endswith(b"}\n"))
        self.assertFalse(scenario_bytes.endswith(b"}\n\n"))
        self.assertEqual(
            binding["resources"]["golden_scenario"]["sha256"],
            f"sha256:{sha256(scenario_bytes).hexdigest()}",
        )

    def test_shared_golden_journey_drives_emitted_observation(self) -> None:
        scenario = load_golden_specimen_scenario()
        bundle = self.simulate(scenario=scenario)
        observation = validate_golden_specimen_observation(bundle["observation"])

        self.assertEqual(
            len(bundle["result"]["specimen"]["audit"]),
            len(scenario["commands"]),
        )
        self.assertEqual(observation["scenario_id"], scenario["scenario_id"])
        projection = observation["result"]["projection"]
        self.assertEqual(
            projection["lifecycle"]["aggregate_version"],
            scenario["expected_state"]["aggregate_version"],
        )
        self.assertEqual(
            projection["measurement"],
            scenario["expected_state"]["result"],
        )
        self.assertEqual(bundle["observation_digest"], canonical_digest(observation))
        execution = bundle["scenario_execution"]
        self.assertEqual(execution["scenario_id"], scenario["scenario_id"])
        self.assertEqual(
            [item["actor_id"] for item in execution["commands"]],
            [item["actor_id"] for item in scenario["commands"]],
        )
        self.assertEqual(
            [item["occurred_at"] for item in execution["commands"]],
            [item["occurred_at"] for item in scenario["commands"]],
        )
        self.assertEqual(
            bundle["scenario_execution_digest"],
            canonical_digest(execution),
        )
        release = json.loads((ROOT / "release" / "repository-role.json").read_text())
        self.assertEqual(
            release["reference_simulation_observation_digest"],
            bundle["observation_digest"],
        )
        self.assertEqual(
            release["reference_scenario_execution_digest"],
            bundle["scenario_execution_digest"],
        )

        revised = deepcopy(scenario)
        revised["commands"][-1]["action"] = "void"
        with self.assertRaisesRegex(ValueError, "released contract digest"):
            self.simulate(scenario=revised)

    def test_golden_observation_keeps_the_generic_envelope_boundary_available(self) -> None:
        specific = self.golden_observation()
        validated = validate_golden_specimen_observation(specific)
        self.assertEqual(validated, specific)

        generic = deepcopy(specific)
        generic.pop("scenario_version")
        generic.pop("scenario_digest")
        generic["result"] = {"producer_owned_result": "available"}
        self.assertEqual(validate_observation_v1(generic), generic)

        with self.assertRaisesRegex(
            ContractBoundaryError,
            "requires fields: scenario_digest, scenario_version",
        ):
            validate_golden_specimen_observation(generic)

    def test_golden_observation_binds_coordinate_shape_types_and_chronology(self) -> None:
        invalid_cases = []

        wrong_scenario_version = self.golden_observation()
        wrong_scenario_version["scenario_version"] = "1.1.0"
        invalid_cases.append(
            (
                "scenario version",
                wrong_scenario_version,
                "scenario version 1.0.0",
            )
        )

        wrong_scenario_digest = self.golden_observation()
        wrong_scenario_digest["scenario_digest"] = "sha256:" + "0" * 64
        invalid_cases.append(
            (
                "scenario model digest",
                wrong_scenario_digest,
                "released scenario model digest",
            )
        )

        wrong_projection_identity = self.golden_observation()
        wrong_projection_identity["result"]["projection"]["projection_id"] = (
            "urn:driftframe:lims-eln:another-result"
        )
        invalid_cases.append(
            (
                "projection identity",
                wrong_projection_identity,
                "released Golden Specimen projection identity",
            )
        )

        wrong_projection_version = self.golden_observation()
        wrong_projection_version["result"]["projection"][
            "projection_version"
        ] = "1.1.0"
        invalid_cases.append(
            (
                "projection version",
                wrong_projection_version,
                "projection version 1.0.0",
            )
        )

        wrong_compatibility = self.golden_observation()
        wrong_compatibility["result"]["projection"][
            "comparison_compatibility"
        ] = "additive"
        invalid_cases.append(
            (
                "comparison compatibility",
                wrong_compatibility,
                "exact-version comparison compatibility",
            )
        )

        extra_projection_field = self.golden_observation()
        extra_projection_field["result"]["projection"]["display_label"] = (
            "Golden specimen"
        )
        invalid_cases.append(
            (
                "closed projection",
                extra_projection_field,
                "fields use the released contract",
            )
        )

        boolean_version = self.golden_observation()
        boolean_version["result"]["projection"]["lifecycle"][
            "aggregate_version"
        ] = True
        invalid_cases.append(
            (
                "positive integer",
                boolean_version,
                "carries a positive integer",
            )
        )

        release_before_review = self.golden_observation()
        release_before_review["result"]["projection"]["release"][
            "released_at"
        ] = "2026-08-17T14:34:59Z"
        invalid_cases.append(
            (
                "ordered review and release",
                release_before_review,
                "review resolution precedes release",
            )
        )

        impossible_review_date = self.golden_observation()
        impossible_review_date["result"]["projection"]["review_resolution"][
            "resolved_at"
        ] = "2026-02-30T14:35:00Z"
        invalid_cases.append(
            (
                "calendar timestamp",
                impossible_review_date,
                "names a valid UTC calendar instant",
            )
        )

        for label, payload, message in invalid_cases:
            with self.subTest(label=label):
                with self.assertRaisesRegex(ContractBoundaryError, message):
                    validate_golden_specimen_observation(payload)

    def test_golden_observation_defaults_only_producer_owned_detail(self) -> None:
        value = self.golden_observation()
        del value["result"]["producer_detail"]
        validated = validate_golden_specimen_observation(value)
        self.assertEqual(validated["result"]["producer_detail"], {})

        wrong_type = self.golden_observation()
        wrong_type["result"]["producer_detail"] = []
        with self.assertRaisesRegex(
            ContractBoundaryError,
            "result.producer_detail carries one JSON object",
        ):
            validate_golden_specimen_observation(wrong_type)

    @unittest.skipUnless(
        SPECIFICATION_BOUNDARY_AVAILABLE,
        "an authoritative Program package or sibling source and its Pydantic runtime are available through the focused conformance path",
    )
    def test_authoritative_package_accepts_emitted_observation(self) -> None:
        use_sibling_source = not INSTALLED_SPECIFICATION_AVAILABLE
        if use_sibling_source:
            sys.path.insert(0, str(SPECIFICATION_SOURCE))
        try:
            summary = verify_shared_package()
            bundle = self.simulate()
            standalone_value = validate_golden_specimen_observation(
                bundle["observation"]
            )
            shared_value = validate_with_shared_package(standalone_value)
        finally:
            if use_sibling_source:
                sys.path.remove(str(SPECIFICATION_SOURCE))

        self.assertEqual(summary, contract_reference())
        self.assertEqual(shared_value, standalone_value)

        drifted = deepcopy(standalone_value)
        drifted["result"]["projection"]["comparison_compatibility"] = (
            "additive"
        )
        if use_sibling_source:
            sys.path.insert(0, str(SPECIFICATION_SOURCE))
        try:
            with self.assertRaises(ValueError):
                validate_with_shared_package(drifted)
        finally:
            if use_sibling_source:
                sys.path.remove(str(SPECIFICATION_SOURCE))


if __name__ == "__main__":
    unittest.main()
