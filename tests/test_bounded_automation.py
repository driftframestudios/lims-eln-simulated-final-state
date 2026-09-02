"""Material mutation probes for the bounded hosted-automation contract."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import sys
import unittest


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "simulation_check_bounded_automation",
    ROOT / "tools" / "check_bounded_automation.py",
)
assert SPEC and SPEC.loader
checker = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = checker
SPEC.loader.exec_module(checker)


class BoundedAutomationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.workflow = (ROOT / ".github/workflows/pull-request.yml").read_text(
            encoding="utf-8"
        )
        cls.dependabot = (ROOT / ".github/dependabot.yml").read_text(
            encoding="utf-8"
        )

    def workflow_mutation(self, before: str, after: str) -> list[str]:
        self.assertIn(before, self.workflow)
        return checker.validate_pull_request_workflow(
            self.workflow.replace(before, after, 1)
        )

    def dependabot_mutation(self, before: str, after: str) -> list[str]:
        self.assertIn(before, self.dependabot)
        return checker.validate_dependabot(self.dependabot.replace(before, after, 1))

    def test_current_sources_match_contract(self) -> None:
        manifest = json.loads(
            (ROOT / "release/repository-role.json").read_text(encoding="utf-8")
        )
        self.assertEqual([], checker.validate_pull_request_workflow(self.workflow))
        self.assertEqual([], checker.validate_dependabot(self.dependabot))
        self.assertEqual(
            [],
            checker.validate_repository_automation(
                ROOT, manifest["automation_controls"]
            ),
        )

    def test_manifest_projection_is_bound_to_source_contract(self) -> None:
        broadened = dict(checker.EXPECTED_AUTOMATION_CONTROLS)
        broadened["pull_request_permissions"] = {
            "contents": "read",
            "issues": "write",
        }
        self.assertTrue(checker.validate_repository_automation(ROOT, broadened))
        self.assertTrue(checker.validate_repository_automation(ROOT, None))

    def test_permission_and_fail_closed_mutations_are_visible(self) -> None:
        mutations = (
            ("  contents: read", "  contents: read\n  issues: write"),
            (
                "    timeout-minutes: 10",
                "    permissions:\n      contents: write\n    timeout-minutes: 10",
            ),
            (
                "    timeout-minutes: 10",
                '    "permissions": {issues: write}\n    timeout-minutes: 10',
            ),
            (
                "        run: python tools/validate_repository.py",
                "        continue-on-error: true\n        run: python tools/validate_repository.py",
            ),
            ("  cancel-in-progress: true", "  cancel-in-progress: false"),
            (
                "    timeout-minutes: 10",
                "    timeout-minutes: 11\n    # timeout-minutes: 10",
            ),
        )
        for before, after in mutations:
            with self.subTest(after=after):
                self.assertTrue(self.workflow_mutation(before, after))

    def test_trigger_job_and_action_mutations_are_visible(self) -> None:
        mutations = (
            ("      - main", "      - release"),
            (
                "jobs:\n  repository-validation:",
                "jobs:\n  remote-proof:\n    uses: owner/repo/.github/workflows/proof.yml@main\n"
                "  repository-validation:",
            ),
            (
                "actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1",
                "actions/checkout@main",
            ),
            (
                "actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1",
                "actions/checkout@1111111111111111111111111111111111111111\n"
                "        # uses: actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1",
            ),
            (
                "actions/setup-python@5fda3b95a4ea91299a34e894583c3862153e4b97",
                "vendor/setup-python@5fda3b95a4ea91299a34e894583c3862153e4b97",
            ),
            ("          fetch-depth: 0", "          fetch-depth: 1"),
            (
                '          python-version: "3.12"',
                '          python-version: "3.12"\n'
                "          token: ${{ secrets['AUTOMATION_TOKEN'] }}",
            ),
            (
                "      - name: Validate repository evidence contracts",
                '      - run: echo "${{ secrets[\'AUTOMATION_TOKEN\'] }}"\n'
                "      - name: Validate repository evidence contracts",
            ),
            (
                "        run: python tools/validate_repository.py",
                "        run: python tools/validate_repository.py --quick\n"
                "        # run: python tools/validate_repository.py",
            ),
            (
                "        run: python tools/verify_release_coordinate.py",
                "        run: python tools/verify_release_coordinate.py --accepted-ref HEAD",
            ),
        )
        for before, after in mutations:
            with self.subTest(after=after):
                self.assertTrue(self.workflow_mutation(before, after))

    def test_dependabot_scope_mutations_are_visible(self) -> None:
        mutations = (
            ("    target-branch: develop", "    target-branch: main"),
            ("      interval: monthly", "      interval: weekly"),
            ("    open-pull-requests-limit: 2", "    open-pull-requests-limit: 3"),
            ("          - patch", "          - major"),
            (
                "      github-actions-minor-patch:",
                "      renamed-group:",
            ),
            (
                "    directory: /",
                '    directory: /\n    "directory": /wrong',
            ),
            (
                "  - package-ecosystem: github-actions",
                "  - package-ecosystem: pip\n"
                "    directory: /\n"
                "    target-branch: develop\n"
                "    schedule:\n"
                "      interval: monthly\n"
                "    open-pull-requests-limit: 2\n"
                "    groups:\n"
                "      pip-minor-patch:\n"
                "        patterns:\n"
                "          - \"*\"\n"
                "        update-types:\n"
                "          - minor\n"
                "          - patch\n"
                "  - package-ecosystem: github-actions",
            ),
            (
                "  - package-ecosystem: github-actions",
                '  - {package-ecosystem: pip, directory: /wrong, target-branch: main, '
                "schedule: {interval: daily}, open-pull-requests-limit: 20}\n"
                "  - package-ecosystem: github-actions",
            ),
        )
        for before, after in mutations:
            with self.subTest(after=after):
                self.assertTrue(self.dependabot_mutation(before, after))


if __name__ == "__main__":
    unittest.main()
