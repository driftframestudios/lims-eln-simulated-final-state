# Contribution and forecast discipline

Start bounded work from `develop` using `feature/<decision-or-scenario>`. Open a pull
request into `develop` with the affected specification IDs, assumptions, falsifiers,
and expected material effects. A release branch freezes fixtures and decision inputs.

A correction to a released forecast uses `hotfix/<forecast-defect>`, targets `main`,
and is merged back into `develop`. The correction creates a new release. The earlier
release remains available for calibration.

Each change preserves these qualities:

1. Synthetic data provenance is machine-readable.
2. `evidence_mode` remains `simulated`.
3. Decisions include alternatives, assumptions, probability, and falsifiers.
4. Scenarios pair ordinary behavior with boundary, failure, and recovery behavior.
5. Code comments state the desired behavior and replacement path.
6. The package imports repository-local modules and Python standard-library modules.

