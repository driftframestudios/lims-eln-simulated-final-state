# LIMS/ELN Simulated Final State

This repository is an independently runnable counterfactual for a mature laboratory
integration platform. It lets a hybrid team inspect a complete forecast before the
delivery system reaches the same decisions.

The runtime resolves entirely from this repository, Python's standard library, and
synthetic fixtures. The actual implementation remains an independent system. Ideas
move from this simulation into delivery through reviewed decisions and released
specifications.

## Epistemic boundary

Every generated record declares:

```json
{
  "evidence_mode": "simulated",
  "simulation_authority": "advisory_only",
  "accountable_observation_required": true
}
```

The simulation models a projected accepted state. Accountable scientific, Quality,
Regulatory, security, and operational decisions are produced only from observed
evidence in named environments. The comparative-evidence repository performs that
admission.

## What the simulation covers

- accession, custody, instrument ingestion, review, release, and correction;
- Sapio, Benchling, and LabKey behavior through deterministic emulators;
- stable-request reconciliation after ambiguous vendor writes;
- representative migration, rollback, clean restore, and data exit;
- tenant authorization, trace redaction, telemetry, and incident exercises;
- draft scientific, Quality, Regulatory, security, and operations acceptance packets;
- assumptions, forecasts, decisions, falsifiers, and simulated receipt manifests.

## Run it

```bash
python -m unittest discover -s tests -v
PYTHONPATH=src python -m lims_eln_sim.cli \
  --fixture fixtures/golden-specimen.json \
  --output build/simulation
```

The command writes a deterministic `result.json`, receipt bundle, migration report,
restore report, security exercise, telemetry summary, and acceptance drafts.

## Branching

This repository uses a GitFlow-like pattern:

- `main` contains released forecast baselines.
- `develop` integrates the next forecast.
- `feature/*` carries bounded scenario or model work.
- `release/*` freezes comparison inputs and accepts stabilization changes.
- `hotfix/*` repairs a released simulation defect and returns the correction to
  `develop`.

Release tags use `forecast-YYYY-QN-rN`. Published baselines remain immutable so later
comparisons preserve what the team believed at the time.

## Safety and privacy posture

Synthetic fixtures are the only permitted data class in this repository. A fixture
that resembles an external record is replaced with a generated identity, generated
timestamps, and generated artifacts before it enters version control. Secrets are
represented by stable placeholders. Runtime traces retain correlation and outcome
fields while sensitive values are replaced with classification labels and digests.

