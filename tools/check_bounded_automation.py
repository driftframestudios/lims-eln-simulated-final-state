#!/usr/bin/env python3
"""Validate the canonical, deliberately small hosted-automation grammar.

These control files accept one repository-owned YAML spelling. Blank lines and
whole-line comments are presentation only; every other line participates in
the contract. A valid YAML construct outside this grammar therefore produces a
finding instead of disappearing during partial parsing.
"""

from __future__ import annotations

from itertools import zip_longest
from pathlib import Path
import re


ROOT = Path(__file__).resolve().parents[1]
WORKFLOW_PATH = ROOT / ".github/workflows/pull-request.yml"
DEPENDABOT_PATH = ROOT / ".github/dependabot.yml"

CHECKOUT_REVISION = "3d3c42e5aac5ba805825da76410c181273ba90b1"
SETUP_PYTHON_REVISION = "5fda3b95a4ea91299a34e894583c3862153e4b97"

EXPECTED_WORKFLOW_LINES = (
    "name: pull-request-proof",
    "on:",
    "  pull_request:",
    "    branches:",
    "      - develop",
    "      - main",
    "permissions:",
    "  contents: read",
    "concurrency:",
    "  group: simulation-pr-${{ github.event.pull_request.number }}",
    "  cancel-in-progress: true",
    "jobs:",
    "  repository-validation:",
    "    name: Repository validation",
    "    runs-on: ubuntu-24.04",
    "    timeout-minutes: 10",
    "    steps:",
    "      - name: Check out source",
    f"        uses: actions/checkout@{CHECKOUT_REVISION}",
    "        with:",
    "          persist-credentials: false",
    "          fetch-depth: 0",
    "      - name: Select Python",
    f"        uses: actions/setup-python@{SETUP_PYTHON_REVISION}",
    "        with:",
    '          python-version: "3.12"',
    "      - name: Exercise selected-future behavior and boundaries",
    "        run: python -m unittest discover -s tests -v",
    "      - name: Validate repository evidence contracts",
    "        run: python tools/validate_repository.py",
    "      - name: Verify signed release coordinate",
    "        run: python tools/verify_release_coordinate.py",
)

EXPECTED_DEPENDABOT_LINES = (
    "version: 2",
    "updates:",
    "  - package-ecosystem: github-actions",
    "    directory: /",
    "    target-branch: develop",
    "    schedule:",
    "      interval: monthly",
    "    open-pull-requests-limit: 2",
    "    groups:",
    "      github-actions-minor-patch:",
    "        patterns:",
    '          - "*"',
    "        update-types:",
    "          - minor",
    "          - patch",
)

EXPECTED_AUTOMATION_CONTROLS = {
    "pull_request_workflow": ".github/workflows/pull-request.yml",
    "pull_request_targets": ["develop", "main"],
    "pull_request_runner": "ubuntu-24.04",
    "pull_request_python": "3.12",
    "pull_request_timeout_minutes": 10,
    "pull_request_permissions": {"contents": "read"},
    "pull_request_actions": {
        "actions/checkout": CHECKOUT_REVISION,
        "actions/setup-python": SETUP_PYTHON_REVISION,
    },
    "pull_request_concurrency_cancellation": True,
    "release_coordinate_verifier": "tools/verify_release_coordinate.py",
    "release_coordinate_fetch_depth": 0,
    "manual_full_proof_workflow": ".github/workflows/verify.yml",
    "dependabot_configuration": ".github/dependabot.yml",
    "dependabot_target": "develop",
    "dependabot_interval": "monthly",
    "dependabot_open_pull_requests_per_ecosystem": 2,
    "dependabot_grouped_update_types": ["minor", "patch"],
    "monthly_budget_minutes": {"minimum": 100, "maximum": 300},
    "settings_state": "pull_request_proof_active_with_release_coordinate_verification",
}

_SECRET_EXPRESSION = re.compile(
    r"\$\{\{\s*secrets(?:\.|\s*\[)", flags=re.IGNORECASE
)
_UNSET = object()


def _contract_lines(source: str, label: str) -> tuple[tuple[str, ...], list[str]]:
    """Return every meaningful line and formatting findings."""
    lines: list[str] = []
    findings: list[str] = []
    for number, raw_line in enumerate(source.splitlines(), start=1):
        if "\t" in raw_line:
            findings.append(f"{label} line {number} uses a tab")
        if raw_line != raw_line.rstrip():
            findings.append(f"{label} line {number} has trailing whitespace")
        line = raw_line.rstrip()
        if not line or line.lstrip().startswith("#"):
            continue
        if "#" in line:
            findings.append(
                f"{label} line {number} uses an inline comment outside the canonical grammar"
            )
        lines.append(line)
    return tuple(lines), findings


def _compare(
    actual: tuple[str, ...], expected: tuple[str, ...], label: str
) -> list[str]:
    if actual == expected:
        return []
    for number, (actual_line, expected_line) in enumerate(
        zip_longest(actual, expected), start=1
    ):
        if actual_line != expected_line:
            return [
                f"{label} line {number} differs from the canonical bounded grammar"
            ]
    return [f"{label} differs from the canonical bounded grammar"]


def validate_pull_request_workflow(source: str) -> list[str]:
    """Return material differences from the exact pull-request proof."""
    actual, findings = _contract_lines(source, "pull-request workflow")
    findings.extend(_compare(actual, EXPECTED_WORKFLOW_LINES, "pull-request workflow"))
    if _SECRET_EXPRESSION.search(source):
        findings.append("pull-request workflow contains a secret expression")
    return findings


def validate_dependabot(source: str) -> list[str]:
    """Return material differences from the exact maintenance stream."""
    actual, findings = _contract_lines(source, "Dependabot configuration")
    findings.extend(_compare(actual, EXPECTED_DEPENDABOT_LINES, "Dependabot configuration"))
    return findings


def validate_repository_automation(
    root: Path = ROOT, declared_controls: object = _UNSET
) -> list[str]:
    """Validate the source controls and their release-manifest projection."""
    workflow = (root / WORKFLOW_PATH.relative_to(ROOT)).read_text(encoding="utf-8")
    dependabot = (root / DEPENDABOT_PATH.relative_to(ROOT)).read_text(encoding="utf-8")
    findings = [
        *validate_pull_request_workflow(workflow),
        *validate_dependabot(dependabot),
    ]
    if declared_controls is not _UNSET and declared_controls != EXPECTED_AUTOMATION_CONTROLS:
        findings.append(
            "release automation_controls differs from the canonical source contract"
        )
    return findings


def main() -> int:
    findings = validate_repository_automation()
    if findings:
        print("Bounded automation differs from its source contract:")
        for finding in findings:
            print(f"  - {finding}")
        return 1
    print("Bounded automation source contract passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
