# Contribution and forecast discipline

Start bounded work from `develop` using `feature/<decision-or-scenario>`. Open a pull
request into `develop` with the affected specification IDs, assumptions, falsifiers,
and expected material effects. A release branch freezes fixtures and decision inputs.

A correction to a released forecast uses `hotfix/<forecast-defect>`, targets `main`,
and is merged back into `develop`. The correction creates a new release. The earlier
release remains available for calibration.

Local forecast tests remain the standing proof path. The repository allocates
100–300 hosted runner minutes per month. One read-only, cancellable Python 3.12
proof accompanies pull requests into `develop` and `main`. The confirmed
`verify-simulated-final-state` dispatch preserves the three-version matrix,
generated bundle, artifact check, and optional one-day retention when a named
receiver sets `ENABLE_GITHUB_ACTIONS=true` and selects `confirm_run`.

`.github/dependabot.yml` supplies monthly GitHub Actions version updates into
`develop`, with at most two open pull requests. Minor and patch updates share
one bounded pull request; major updates retain separate review and recovery
coordinates. Default-branch security updates retain their `main` route.
Dependabot uses the complete
`dependabot/github_actions/<dependency-update>` grammar with
`dependabot[bot]`; Renovate uses `renovate/<dependency-update>` with
`renovate[bot]`. Each branch identity and target agree with the repository
checker. Each update receives the executable local forecast tests and human
review. A security update accepted on `main` is reconciled into `develop`.

Each change preserves these qualities:

1. Synthetic data provenance is machine-readable.
2. `evidence_mode` remains `simulated`.
3. Decisions include alternatives, assumptions, probability, and falsifiers.
4. Scenarios pair ordinary behavior with boundary, failure, and recovery behavior.
5. Code comments state the desired behavior and replacement path.
6. The package imports repository-local modules and Python standard-library modules.
