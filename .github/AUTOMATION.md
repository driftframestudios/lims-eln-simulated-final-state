# Bounded hosted automation

## Pull-request proof

The repository allocates **100–300 GitHub-hosted runner minutes per month**.
`pull-request-proof` gives pull requests into `develop` and `main` one
review-visible check on Python 3.12. It uses one standard runner, read-only
repository permission, a ten-minute ceiling, and cancellation for a superseded
run. The repository tests and aggregate validator exercise selected-future
behavior, deterministic artifacts, strict ingress, release alignment, and
repository safety together. A full-history, credential-free checkout also lets
`tools/verify_release_coordinate.py` reproduce the signed tag, accepted Git
objects, archive bytes, approved signing-key fingerprint, and exact observation
receipt. A dependency-free, restricted YAML checker reads the workflow and
maintenance configuration as control data; mutation probes keep widened
permissions, jobs, triggers, failure behavior, and dependency scope visible.

The workflow is active and has produced the exact `Repository validation`
context. Repository settings remain the authority for deciding whether that
context is required for a receiving branch.

## Confirmed full proof

`verify-simulated-final-state` retains the Python 3.11–3.13 matrix, generated
forecast bundle, artifact-boundary check, optional one-day retention, stable
matrix-result check, and final signed-coordinate verification from a full Git
checkout. A named receiver can run it by setting
`ENABLE_GITHUB_ACTIONS=true`, selecting `confirm_run`, and dispatching the
workflow when that broader evidence is useful.

## Monthly dependency upkeep

`.github/dependabot.yml` checks pinned GitHub Actions monthly. Version-update
pull requests target `develop`, at most two remain open, and minor and patch
updates share one reviewable group. Major updates retain an individual review
coordinate. GitHub reads this configuration from the default branch, so the
reviewed schedule begins after release promotion to `main` and sends its
version-update pull requests back to `develop`.

## Recovery

Local forecast tests, `python3 tools/validate_repository.py`, and
`python3 tools/verify_release_coordinate.py` remain the standing source-owned
evidence. The first two checks operate from ordinary source; the release
coordinate check uses a full Git checkout containing the signed tag. Setting
`ENABLE_GITHUB_ACTIONS=false` rests the confirmed full proof. Repository
settings can pause all hosted execution. A reviewed source change can return
the dependency schedule to its manual filename while preserving the ecosystem
and branch contract.
