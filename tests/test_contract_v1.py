from __future__ import annotations

from copy import deepcopy
from hashlib import sha256
import json
from pathlib import Path
import sys
import tomllib
import unittest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from lims_eln_sim.contract_v1 import (
    CONTRACT_DISTRIBUTION_VERSION,
    canonical_digest,
    contract_reference,
    load_contract_binding,
    load_golden_specimen_scenario,
    load_observation_schema,
    validate_observation_v1,
    validate_with_shared_package,
    verify_shared_package,
)
from lims_eln_sim.safety import synthetic_redaction_key
from lims_eln_sim.simulation import run


SPECIFICATION_SOURCE = (
    ROOT.parent / "lims-eln-program-specification" / "src"
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
        cls.redaction_key = synthetic_redaction_key(cls.fixture["redaction_key_id"])

    def simulate(self, *, scenario: dict | None = None) -> dict:
        return run(
            self.fixture,
            intended_use_profile=self.intended_use_profile,
            migration_corpus=self.migration_corpus,
            redaction_key=self.redaction_key,
            scenario=scenario,
        )

    def test_bound_snapshots_retain_released_version_and_digests(self) -> None:
        binding = load_contract_binding()
        scenario = load_golden_specimen_scenario()
        schema = load_observation_schema()
        release = json.loads((ROOT / "release" / "repository-role.json").read_text())

        self.assertEqual(binding["contract_version"], "1.0.0")
        self.assertEqual(scenario["scenario_id"], "SCN-GOLDEN-SPECIMEN-001")
        self.assertEqual(
            schema["$id"],
            "urn:driftframe:lims-eln:observation-envelope:1.0.0",
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
        observation = validate_observation_v1(bundle["observation"])

        self.assertEqual(len(bundle["result"]["specimen"]["audit"]), len(scenario["commands"]))
        self.assertEqual(observation["scenario_id"], scenario["scenario_id"])
        self.assertEqual(
            observation["result"]["specimen"]["revision"],
            scenario["expected_state"]["aggregate_version"],
        )
        self.assertEqual(
            observation["result"]["specimen"]["result"],
            {
                "unit": scenario["expected_state"]["result"]["unit"],
                "quality_flag": scenario["expected_state"]["result"]["quality_flag"],
            },
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

    @unittest.skipUnless(
        SPECIFICATION_SOURCE.is_dir(),
        "authoritative sibling source is available through the focused conformance path",
    )
    def test_authoritative_package_accepts_emitted_observation(self) -> None:
        sys.path.insert(0, str(SPECIFICATION_SOURCE))
        try:
            summary = verify_shared_package()
            bundle = self.simulate()
            shared_value = validate_with_shared_package(bundle["observation"])
        finally:
            sys.path.remove(str(SPECIFICATION_SOURCE))

        self.assertEqual(summary, contract_reference())
        self.assertEqual(shared_value, bundle["observation"])


if __name__ == "__main__":
    unittest.main()
