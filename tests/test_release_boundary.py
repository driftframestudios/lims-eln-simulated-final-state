"""Behavior checks for selected-future release alignment."""

from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path
import re
import sys
import tomllib
import unittest


ROOT = Path(__file__).resolve().parents[1]
COMPANY = "Driftframe Studios, Limited Liability Company"
APPROVED_PERSONAL_NAME_CARRIERS = {"AUTHORS"}
IGNORED_ATTRIBUTION_PARTS = {
    ".git",
    ".pytest_cache",
    ".venv",
    "__pycache__",
    "build",
    "dist",
}
sys.path.insert(0, str(ROOT / "src"))

from lims_eln_sim.release_boundary import (  # noqa: E402
    ReleaseBoundaryError,
    validate_release_alignment,
)
from lims_eln_sim.safety import synthetic_redaction_key  # noqa: E402
from lims_eln_sim.simulation import FORECAST_METADATA, run  # noqa: E402


def _personal_name(authors: str) -> str:
    match = re.search(
        r"is authored by (?P<name>[^\n]+) and\s+maintained by",
        authors,
    )
    if match is None:
        raise AssertionError("AUTHORS requires an explicit personal authorship entry")
    name = match.group("name").strip()
    if len(name.split()) < 2:
        raise AssertionError("AUTHORS requires an unambiguous personal name")
    return name


def _observed_personal_name_carriers(personal_name: str) -> set[str]:
    pattern = re.compile(
        rf"(?<!\w){re.escape(personal_name)}(?!\w)",
        re.IGNORECASE,
    )
    carriers: set[str] = set()
    for path in sorted(ROOT.rglob("*")):
        if (
            not path.is_file()
            or path.is_symlink()
            or any(part in IGNORED_ATTRIBUTION_PARTS for part in path.parts)
        ):
            continue
        try:
            content = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        if pattern.search(content):
            carriers.add(path.relative_to(ROOT).as_posix())
    return carriers


class ReleaseBoundaryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        fixture = cls._load("fixtures/golden-specimen.json")
        cls.result = run(
            fixture,
            intended_use_profile=cls._load(
                "specification/intended-use-and-applicability-profile.json"
            ),
            migration_corpus=cls._load(
                "fixtures/representative-migration-corpus.json"
            ),
            database_oracle=cls._load(
                "database/final-state-database-oracle-v1.json"
            ),
            redaction_key=synthetic_redaction_key(fixture["redaction_key_id"]),
        )

    @staticmethod
    def _load(relative: str) -> dict:
        return json.loads((ROOT / relative).read_text(encoding="utf-8"))

    def documents(self) -> dict[str, object]:
        return {
            "metadata": deepcopy(FORECAST_METADATA),
            "closure": deepcopy(self.result["governance_closure"]),
            "receipts": deepcopy(self.result["receipts"]),
            "bounded": deepcopy(self.result["result"]["bounded_caller"]),
            "assumptions": self._load("ledgers/assumptions.json"),
            "manifest": self._load("release/repository-role.json"),
            "first": self._load("first-receipt.json"),
            "machine": self._load("machine-node.json"),
            "horizon": self._load("COORDINATION-HORIZON.json"),
        }

    def assert_aligned(self, documents: dict[str, object]) -> None:
        validate_release_alignment(
            forecast_metadata=documents["metadata"],
            governance_closure=documents["closure"],
            detailed_receipts=documents["receipts"],
            bounded_caller=documents["bounded"],
            assumptions_ledger=documents["assumptions"],
            release_manifest=documents["manifest"],
            first_receipt=documents["first"],
            machine_node=documents["machine"],
            coordination_horizon=documents["horizon"],
        )

    def test_repository_carriers_share_one_selected_future(self) -> None:
        self.assert_aligned(self.documents())

    def test_repository_and_package_carry_confirmed_provenance(self) -> None:
        authors = (ROOT / "AUTHORS").read_text(encoding="utf-8")
        package = tomllib.loads(
            (ROOT / "pyproject.toml").read_text(encoding="utf-8")
        )["project"]
        self.assertIn(COMPANY, authors)
        self.assertEqual(
            package["authors"],
            [{"name": COMPANY}],
        )
        self.assertEqual(package["license"], {"text": "Apache-2.0"})
        self.assertEqual(package["readme"], "README.md")
        self.assertEqual(
            _observed_personal_name_carriers(_personal_name(authors)),
            APPROVED_PERSONAL_NAME_CARRIERS,
        )

    def test_selected_future_assumption_ids_keep_one_definition(self) -> None:
        mutations = (
            ("assumptions", ("assumptions",), "assumption ledger IDs"),
            (
                "closure",
                ("future_reality", "assumption_ids"),
                "governance selected-future assumption IDs",
            ),
            (
                "first",
                ("selected_future", "assumption_ids"),
                "first receipt selected-future assumption IDs",
            ),
        )
        for carrier, path, message in mutations:
            with self.subTest(carrier=carrier):
                documents = self.documents()
                values = _resolve(documents[carrier], path)
                if carrier == "assumptions":
                    values.append(deepcopy(values[0]))
                else:
                    values.append(values[0])
                with self.assertRaisesRegex(
                    ReleaseBoundaryError,
                    re.escape(message) + ".*one definition",
                ):
                    self.assert_aligned(documents)

    def test_release_posture_mutations_return_to_forecast_authority(self) -> None:
        mutations = (
            (
                "assumptions",
                ("future_reality_id",),
                "FUTURE-REALITY-CHANGED",
                "assumption ledger future_reality_id",
            ),
            (
                "assumptions",
                ("future_reality_version",),
                "future-reality-2029-01-01-v1",
                "assumption ledger future_reality_version",
            ),
            (
                "assumptions",
                ("authority",),
                "observed",
                "assumption ledger authority",
            ),
            (
                "assumptions",
                ("assumptions", 0, "evidence_mode"),
                "observed",
                "assumptions[0] evidence mode",
            ),
            (
                "closure",
                ("evidence_mode",),
                "observed",
                "governance closure evidence_mode",
            ),
            (
                "closure",
                ("environment_observed_closure",),
                "closed",
                "governance closure environment_observed_closure",
            ),
            (
                "receipts",
                (0, "evidence_mode"),
                "observed",
                "detailed receipts[0] evidence_mode",
            ),
            (
                "receipts",
                (0, "reality_basis", "kind"),
                "environment_observed",
                "detailed receipts[0] reality basis kind",
            ),
            (
                "receipts",
                (0, "reality_basis", "authority"),
                "observed",
                "detailed receipts[0] reality basis authority",
            ),
            (
                "receipts",
                (0, "reality_basis", "production_authorization_effect"),
                "authorized",
                "detailed receipts[0] reality basis production_authorization_effect",
            ),
            (
                "manifest",
                ("external_release",),
                "forecast-changed",
                "release manifest forecast release",
            ),
            (
                "manifest",
                ("authority_posture",),
                "observed",
                "release manifest authority posture",
            ),
            (
                "manifest",
                ("first_receipt_contract", "assurance_stage"),
                "accepted",
                "release manifest first-receipt contract",
            ),
        )
        for carrier, path, value, message in mutations:
            with self.subTest(carrier=carrier, path=path):
                documents = self.documents()
                _assign(documents[carrier], path, value)
                with self.assertRaisesRegex(
                    ReleaseBoundaryError,
                    re.escape(message),
                ):
                    self.assert_aligned(documents)

    def test_first_receipt_mutations_preserve_orientation_and_reentry(self) -> None:
        mutations = (
            (
                "first",
                ("selected_future", "future_reality_version"),
                "future-reality-2029-01-01-v1",
                "first receipt selected future",
            ),
            (
                "first",
                ("authority_posture", "simulation_authority"),
                "production",
                "first receipt authority posture simulation_authority",
            ),
            (
                "first",
                ("authority_posture", "accountable_observation_required"),
                True,
                "first receipt authority posture accountable_observation_required",
            ),
            (
                "first",
                ("evidence_posture", 0, "assurance_stage"),
                "specified",
                "first receipt evidence posture[0] assurance stage",
            ),
            (
                "first",
                ("evidence_posture", 2, "status"),
                "active",
                "first receipt evidence posture[2] status",
            ),
            (
                "first",
                ("evidence_posture", 1, "mode"),
                "production",
                "first receipt evidence posture[1] mode",
            ),
            (
                "first",
                ("contract_state", 1, "digest"),
                "sha256:" + "0" * 64,
                "first receipt contract set",
            ),
            (
                "first",
                ("contract_state", 2, "digest"),
                "sha256:" + "0" * 64,
                "first receipt contract set",
            ),
            (
                "machine",
                ("contracts", 1, "digest"),
                "sha256:" + "0" * 64,
                "Machine Node contract set",
            ),
            (
                "machine",
                ("first_receipt_contract_id",),
                "FIRST-RCP-CHANGED",
                "first receipt identity",
            ),
            (
                "first",
                ("machine_node_id",),
                "NODE-OTHER",
                "first receipt Machine Node identity",
            ),
            (
                "machine",
                ("authority", "mode"),
                "production",
                "Machine Node authority mode",
            ),
            (
                "first",
                ("open_receipts",),
                [],
                "first receipt open-receipt IDs",
            ),
            (
                "first",
                ("handoff", "recipient_role"),
                "release automation",
                "first receipt next receiver",
            ),
            (
                "first",
                ("handoff", "action_ids"),
                ["HORIZON-SIMULATION-EXTENSIONS"],
                "first receipt structured handoff actions",
            ),
        )
        for carrier, path, value, message in mutations:
            with self.subTest(carrier=carrier, path=path):
                documents = self.documents()
                _assign(documents[carrier], path, value)
                with self.assertRaisesRegex(
                    ReleaseBoundaryError,
                    re.escape(message),
                ):
                    self.assert_aligned(documents)

    def test_handoff_narrative_can_evolve_behind_stable_action_ids(self) -> None:
        documents = self.documents()
        documents["first"]["handoff"]["next_safe_action"] = (
            "Continue through the named structured action identifiers."
        )
        self.assert_aligned(documents)


def _resolve(value: object, path: tuple[object, ...]) -> object:
    current = value
    for key in path:
        current = current[key]
    return current


def _assign(value: object, path: tuple[object, ...], replacement: object) -> None:
    parent = _resolve(value, path[:-1])
    parent[path[-1]] = replacement


if __name__ == "__main__":
    unittest.main()
