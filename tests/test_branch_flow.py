"""Regression tests for simulation branch coordinates."""

from __future__ import annotations

from contextlib import redirect_stdout
import importlib.util
from io import StringIO
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import textwrap
import unittest


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "simulation_check_branch_flow",
    ROOT / "tools" / "check_branch_flow.py",
)
assert SPEC and SPEC.loader
check_branch_flow = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = check_branch_flow
SPEC.loader.exec_module(check_branch_flow)


def workflow_trigger_keys(workflow: str) -> set[str]:
    """Read the exact top-level event keys from a conventionally formatted workflow."""
    lines = workflow.splitlines()
    start = lines.index("on:") + 1
    triggers: set[str] = set()
    for line in lines[start:]:
        if line and not line.startswith(" "):
            break
        match = re.fullmatch(r"""  ["']?([A-Za-z0-9_-]+)["']?:.*""", line)
        if match:
            triggers.add(match.group(1))
    return triggers


def runner_job_blocks(workflow: str) -> dict[str, str]:
    """Return each job block that allocates a runner."""
    lines = workflow.splitlines()
    start = lines.index("jobs:") + 1
    job_starts = [
        (index, match.group(1))
        for index in range(start, len(lines))
        if (match := re.fullmatch(r"  ([A-Za-z0-9_-]+):", lines[index]))
    ]
    blocks: dict[str, str] = {}
    for position, (index, name) in enumerate(job_starts):
        end = (
            job_starts[position + 1][0]
            if position + 1 < len(job_starts)
            else len(lines)
        )
        block = "\n".join(lines[index:end])
        if re.search(r"(?m)^    runs-on:", block):
            blocks[name] = block
    return blocks


class BranchFlowTests(unittest.TestCase):
    def invoke_workflow(self, base: str, head: str, author: str) -> subprocess.CompletedProcess:
        """Run the source-owned shell step with values from a synthetic PR event."""
        workflow = (ROOT / ".github/workflows/pull-request.yml").read_text(
            encoding="utf-8"
        )
        step_name = "      - name: Check pull-request branch coordinates\n"
        self.assertEqual(1, workflow.count(step_name))
        block = workflow.split(step_name, 1)[1].split("      - name:", 1)[0]
        environment, command = block.split("        run: |\n", 1)
        self.assertTrue(environment.startswith("        env:\n"))
        context = {
            "github": {
                "actor": "re-running-maintainer",
                "event": {
                    "pull_request": {
                        "base": {"ref": base},
                        "head": {"ref": head},
                        "user": {"login": author},
                    }
                },
            }
        }
        selected: dict[str, str] = {}
        for line in environment.splitlines()[1:]:
            match = re.fullmatch(r"          ([A-Z_]+): \$\{\{ ([a-z_.]+) \}\}", line)
            self.assertIsNotNone(match, line)
            assert match is not None
            value = context
            for key in match.group(2).split("."):
                value = value[key]
            selected[match.group(1)] = value
        self.assertEqual({"PR_BASE", "PR_HEAD", "PR_AUTHOR"}, set(selected))
        return subprocess.run(
            ["bash", "--noprofile", "--norc", "-e", "-o", "pipefail", "-c",
             textwrap.dedent(command)],
            cwd=ROOT,
            env={
                **os.environ,
                "PATH": f"{Path(sys.executable).parent}{os.pathsep}{os.environ.get('PATH', '')}",
                **selected,
            },
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        )

    def invoke(self, base: str, head: str, author: str) -> tuple[int, str]:
        output = StringIO()
        with redirect_stdout(output):
            result = check_branch_flow.main(
                ["--base", base, "--head", head, "--author", author]
            )
        return result, output.getvalue()

    def test_non_pull_request_and_partial_coordinates(self) -> None:
        output = StringIO()
        with redirect_stdout(output):
            self.assertEqual(0, check_branch_flow.main([]))
        self.assertIn("non-pull-request", output.getvalue())
        self.assertEqual(
            2,
            self.invoke("", "release/0.3.0", "contributor")[0],
        )

    def test_dependabot_requires_identity_and_target(self) -> None:
        head = "dependabot/github_actions/actions/checkout-5.0.0"
        self.assertEqual(0, self.invoke("develop", head, "dependabot[bot]")[0])
        self.assertEqual(1, self.invoke("develop", head, "contributor")[0])
        self.assertEqual(0, self.invoke("main", head, "dependabot[bot]")[0])
        self.assertEqual(1, self.invoke("release/0.3.0", head, "dependabot[bot]")[0])

    def test_renovate_identity_is_exact(self) -> None:
        result, output = self.invoke(
            "develop", "renovate/github-actions-minor", "renovate[bot]"
        )
        self.assertEqual(0, result)
        self.assertIn("Renovate branch", output)
        self.assertEqual(
            1,
            self.invoke(
                "develop",
                "renovate/github-actions-minor",
                "self-hosted-renovate[bot]",
            )[0],
        )

    def test_malformed_automation_path_is_rejected(self) -> None:
        result, output = self.invoke(
            "main",
            "dependabot/github_actions/actions/../release",
            "dependabot[bot]",
        )
        self.assertEqual(1, result)
        self.assertIn("outside the branch naming contract", output)

    def test_dependency_schedule_matches_branch_grammar(self) -> None:
        config = (ROOT / ".github" / "dependabot.yml").read_text(encoding="utf-8")
        self.assertFalse((ROOT / ".github" / "dependabot.manual.yml").exists())
        configured = {
            item.replace("-", "_")
            for item in re.findall(
                r"^\s*-\s+package-ecosystem:\s*[\"']?([a-z0-9-]+)",
                config,
                flags=re.MULTILINE,
            )
        }
        self.assertEqual(check_branch_flow.DEPENDABOT_BRANCH_ECOSYSTEMS, configured)
        self.assertNotIn("pull-request-branch-name:", config)
        self.assertIn("    target-branch: develop", config)
        self.assertIn("      interval: monthly", config)
        self.assertIn("    open-pull-requests-limit: 2", config)
        self.assertIn("    groups:", config)
        self.assertIn('          - "*"', config)
        self.assertIn("          - minor", config)
        self.assertIn("          - patch", config)
        self.assertEqual(
            1,
            self.invoke(
                "main",
                "dependabot/pip/urllib3-3.0.0",
                "dependabot[bot]",
            )[0],
        )

    def test_feature_branch_routes_through_develop(self) -> None:
        head = "feature/vendor-emulator"
        self.assertEqual(0, self.invoke("develop", head, "contributor")[0])
        self.assertEqual(1, self.invoke("main", head, "contributor")[0])

    def test_actual_workflow_invocation_uses_event_coordinates(self) -> None:
        cases = (
            ("develop", "fix/scenario-repair", "contributor", 0, "Branch-flow check passed"),
            ("develop", "codex/scenario-repair", "contributor", 1, "outside the branch naming contract"),
            ("fix/parent", "fix/scenario-repair", "contributor", 1, "source branch rather than a merge target"),
            ("main", "release/0.4.0", "contributor", 0, "Branch-flow check passed"),
            ("develop", "dependabot/github_actions/actions/checkout-5.0.0", "dependabot[bot]", 0, "Dependabot branch passed"),
            ("develop", "dependabot/github_actions/actions/checkout-5.0.0", "contributor", 1, "requires pull-request author"),
            ("main", "renovate/github-actions-minor", "renovate[bot]", 0, "Renovate branch passed"),
            ("main", "renovate/github-actions-minor", "contributor", 1, "requires pull-request author"),
        )
        for base, head, author, status, message in cases:
            with self.subTest(base=base, head=head, author=author):
                result = self.invoke_workflow(base, head, author)
                self.assertEqual(status, result.returncode, result.stdout + result.stderr)
                self.assertIn(message, result.stdout)
                self.assertEqual("", result.stderr)

    def test_actual_workflow_requires_each_event_coordinate(self) -> None:
        for position in range(3):
            coordinates = ["develop", "fix/scenario-repair", "contributor"]
            coordinates[position] = ""
            with self.subTest(missing=position):
                result = self.invoke_workflow(*coordinates)
                self.assertEqual(2, result.returncode, result.stdout + result.stderr)
                self.assertIn("coordinates together", result.stdout)

    def test_workflow_coordinate_text_stays_one_opaque_shell_argument(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            sentinel = Path(directory) / "shell-side-effect"
            hostile_text = f'fix/"; touch {sentinel}; #\n$(touch {sentinel})\n`touch {sentinel}`'
            for position in range(3):
                coordinates = [
                    "develop",
                    "dependabot/github_actions/actions/checkout-5.0.0",
                    "dependabot[bot]",
                ]
                coordinates[position] = hostile_text
                with self.subTest(coordinate=position):
                    result = self.invoke_workflow(*coordinates)
                    self.assertEqual(1, result.returncode, result.stdout + result.stderr)
                    self.assertIn(repr(hostile_text), result.stdout)
                    self.assertEqual("", result.stderr)
                    self.assertFalse(sentinel.exists())

    def test_full_proof_uses_human_cued_activation_boundary(self) -> None:
        workflow_directory = ROOT / ".github" / "workflows"
        workflow_paths = sorted(
            [*workflow_directory.glob("*.yml"), *workflow_directory.glob("*.yaml")]
        )
        self.assertEqual(
            ["pull-request.yml", "verify.yml"],
            [path.name for path in workflow_paths],
        )
        workflow = (workflow_directory / "verify.yml").read_text(encoding="utf-8")
        self.assertFalse(
            (ROOT / ".github" / "workflows" / "branch-policy.yml").exists()
        )
        self.assertIn("permissions:\n  contents: read", workflow)
        self.assertEqual({"workflow_dispatch"}, workflow_trigger_keys(workflow))
        self.assertIn("confirm_run:", workflow)
        self.assertIn("vars.ENABLE_GITHUB_ACTIONS == 'true'", workflow)
        self.assertIn("inputs.confirm_run", workflow)
        self.assertIn("retain_forecast:", workflow)
        self.assertIn("retention-days: 1", workflow)
        self.assertIn("timeout-minutes: 10", workflow)
        self.assertIn("persist-credentials: false", workflow)
        self.assertEqual(
            1,
            workflow.count(
                "--database-oracle "
                "database/final-state-database-oracle-v1.json"
            ),
        )
        jobs = runner_job_blocks(workflow)
        self.assertTrue(jobs)
        for name, block in jobs.items():
            with self.subTest(job=name):
                gate = re.search(r"(?m)^    if:\s*(.+)$", block)
                self.assertIsNotNone(gate)
                assert gate is not None
                self.assertIn("vars.ENABLE_GITHUB_ACTIONS == 'true'", gate.group(1))
                self.assertIn("inputs.confirm_run", gate.group(1))

    def test_pull_request_workflow_is_bounded_and_read_only(self) -> None:
        workflow = (
            ROOT / ".github" / "workflows" / "pull-request.yml"
        ).read_text(encoding="utf-8")
        self.assertEqual({"pull_request"}, workflow_trigger_keys(workflow))
        self.assertIn("      - develop\n      - main", workflow)
        self.assertIn("permissions:\n  contents: read", workflow)
        self.assertIn("cancel-in-progress: true", workflow)
        self.assertEqual(1, workflow.count("runs-on: ubuntu-24.04"))
        self.assertEqual(1, workflow.count("timeout-minutes: 10"))
        self.assertNotIn("matrix:", workflow)
        self.assertNotIn("services:", workflow)
        self.assertNotIn("actions/upload-artifact", workflow)
        self.assertNotIn("workflow_dispatch:", workflow)
        self.assertNotIn("ENABLE_GITHUB_ACTIONS", workflow)
        self.assertIn(
            "actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1",
            workflow,
        )
        self.assertIn(
            "actions/setup-python@5fda3b95a4ea91299a34e894583c3862153e4b97",
            workflow,
        )
        self.assertIn("fetch-depth: 0", workflow)
        self.assertEqual(1, workflow.count('python-version: "3.12"'))
        self.assertIn("python -m unittest discover -s tests -v", workflow)
        self.assertIn("python tools/validate_repository.py", workflow)
        self.assertIn("python tools/verify_release_coordinate.py", workflow)
        self.assertEqual({"repository-validation"}, set(runner_job_blocks(workflow)))

    def test_release_manifest_records_bounded_automation_source(self) -> None:
        release = json.loads(
            (ROOT / "release" / "repository-role.json").read_text(encoding="utf-8")
        )
        automation = release["automation_controls"]
        self.assertEqual(["develop", "main"], automation["pull_request_targets"])
        self.assertEqual("ubuntu-24.04", automation["pull_request_runner"])
        self.assertEqual("3.12", automation["pull_request_python"])
        self.assertEqual(10, automation["pull_request_timeout_minutes"])
        self.assertEqual({"contents": "read"}, automation["pull_request_permissions"])
        self.assertEqual(
            {
                "actions/checkout": "3d3c42e5aac5ba805825da76410c181273ba90b1",
                "actions/setup-python": "5fda3b95a4ea91299a34e894583c3862153e4b97",
            },
            automation["pull_request_actions"],
        )
        self.assertTrue(automation["pull_request_concurrency_cancellation"])
        self.assertEqual("tools/check_branch_flow.py", automation["branch_flow_checker"])
        self.assertEqual(
            {
                "base": "github.event.pull_request.base.ref",
                "head": "github.event.pull_request.head.ref",
                "author": "github.event.pull_request.user.login",
            },
            automation["branch_flow_coordinate_sources"],
        )
        self.assertEqual(
            "tools/verify_release_coordinate.py",
            automation["release_coordinate_verifier"],
        )
        self.assertEqual(0, automation["release_coordinate_fetch_depth"])
        self.assertEqual("develop", automation["dependabot_target"])
        self.assertEqual(
            {"minimum": 100, "maximum": 300},
            automation["monthly_budget_minutes"],
        )

    def test_control_surfaces_have_explicit_review_ownership(self) -> None:
        owners = (ROOT / "CODEOWNERS").read_text(encoding="utf-8")
        for surface in (
            "/.github/workflows/",
            "/.github/dependabot.yml",
            "/tools/check_branch_flow.py",
            "/tools/check_bounded_automation.py",
            "/tools/verify_release_coordinate.py",
            "/tools/check_artifacts.py",
            "/tests/test_branch_flow.py",
            "/tests/test_bounded_automation.py",
            "/tests/test_release_coordinate.py",
            "/machine-node.json",
            "/first-receipt.json",
            "/COORDINATION-HORIZON.json",
            "/constellation.lock.json",
            "/ledgers/assumptions.json",
        ):
            with self.subTest(surface=surface):
                self.assertIn(surface, owners)


    def test_stable_simulation_context_fails_closed_on_matrix_result(self):
        workflow = (ROOT / ".github" / "workflows" / "verify.yml").read_text(
            encoding="utf-8"
        )
        self.assertIn("\n  simulation-validation:\n", workflow)
        self.assertIn(
            "if: ${{ always() && vars.ENABLE_GITHUB_ACTIONS == 'true' && inputs.confirm_run }}",
            workflow,
        )
        self.assertIn('test "$TEST_RESULT" = "success"', workflow)
        self.assertNotIn("ubuntu-latest", workflow)
        self.assertGreaterEqual(workflow.count("runs-on: ubuntu-24.04"), 2)
        self.assertIn("fail-fast: false", workflow)
        self.assertEqual(1, workflow.count("fetch-depth: 0"))


if __name__ == "__main__":
    unittest.main()
