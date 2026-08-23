# Contribution and forecast discipline

Start bounded work from `develop` using `feature/<decision-or-scenario>`. Open a pull
request into `develop` with the affected specification IDs, assumptions, falsifiers,
and expected material effects. A release branch freezes fixtures and decision inputs.

A correction to a released forecast uses `hotfix/<forecast-defect>`, targets `main`,
and is merged back into `develop`. The correction creates a new release. The earlier
release remains available for calibration.

Local forecast tests are the standing proof path. GitHub Actions rests disabled
in repository settings at a **$0** budget. The manual
`verify-simulated-final-state` workflow becomes available only when a named
human enables Actions, sets `ENABLE_GITHUB_ACTIONS=true`, selects
`confirm_run`, and dispatches it. After the proof is read, set
`ENABLE_GITHUB_ACTIONS=false` and disable Actions in repository settings to
restore the resting state.

Dependency scheduling rests in `.github/dependabot.manual.yml`. A reviewed
rename to `.github/dependabot.yml` activates its monthly cadence. When active,
minor and patch updates may share one bounded pull request; major updates retain
separate review and rollback coordinates. Dependabot uses the complete
`dependabot/github_actions/<dependency-update>` grammar with
`dependabot[bot]`; Renovate uses `renovate/<dependency-update>` with
`renovate[bot]`. Either flow targets `main` or `develop`, and all three
coordinates must agree. Each update receives the executable local forecast
tests and human review. A security update accepted on `main` is reconciled into
`develop`. The repository-local branch checker remains available to reviewers;
the resting state has no automatic branch-policy workflow.

Each change preserves these qualities:

1. Synthetic data provenance is machine-readable.
2. `evidence_mode` remains `simulated`.
3. Decisions include alternatives, assumptions, probability, and falsifiers.
4. Scenarios pair ordinary behavior with boundary, failure, and recovery behavior.
5. Code comments state the desired behavior and replacement path.
6. The package imports repository-local modules and Python standard-library modules.
