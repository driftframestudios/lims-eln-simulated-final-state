# Explore administrative scenarios

Build a reproducible pack that keeps source evidence fixed while administrative
context changes. The pack supplies 18 case families across two authored cohorts,
with two repeats by default: 72 pairs and 144 planned runs. Every run has a
separately authored expectation, and every pair retains its unchanged scientific
evidence. The existing Golden Specimen and signed forecast keep their own identities.

## Quick start

Use Python 3.12 or newer in an isolated environment. The optional extra retrieves
the reviewed Program 0.6.1 source by full commit; private repository access follows
the collaborator's existing Git credential configuration.

```bash
python3 -m venv .venv-admin
.venv-admin/bin/python -m pip install --editable ".[administrative-study]"
.venv-admin/bin/python -m lims_eln_sim.administrative_pack \
  --output build/administrative-pack.json
```

The output contains a Program-admitted study plan, independent expected results,
source identities, construction settings, and the planned cohort matrix. A fresh
destination preserves earlier results. Use `--repeats 1` for the smallest pack;
the supported range is one through four repeats.

Run the complete test suite in this environment with:

```bash
.venv-admin/bin/python -m unittest discover -s tests -v
```

The administrative profile exercises the pack checks and reports the retained
Program 0.3.1 conformance check as skipped. Use a separate environment with
`.[contract-conformance]` for that exact retained proof; its test run reports
the administrative pack checks as skipped. The standard-library core runs the
shared suite with both optional test groups reported as skipped. Import or validation
errors inside an available profile remain visible in the test result.

## What the pack makes inspectable

- Reportability changes with identical supplied scientific information.
- Multi-label classifications, aliases, uncertainty, explicit absence, and abstention.
- Effective dates, policy conflict, pending enrollment, accepted review, amendment,
  and retraction as distinct administrative events.
- Authored language-presentation contrasts with task-relevant information preserved.
- Unchanged-input controls, a known administrative routing effect, and an evaluator
  fault twin whose unchanged oracle can reveal an injected scientific difference.
- Planned failures, exclusions, and pending observations beside completed arms.

The terms and policy are repository-authored examples. Catalog source admission and
real policy interpretation belong to the Enterprise catalog and adapter work.

## Ownership and replay

[`cases.v1.json`](../src/lims_eln_sim/administrative_resources/cases.v1.json) owns
the inputs and expectations. [`administrative_pack.py`](../src/lims_eln_sim/administrative_pack.py)
binds them to Program's immutable study contract. Generation traverses the bounded
matrix in case, cohort, repeat, and arm order. Seed zero identifies this deterministic
construction; randomness is absent from this generator.

Subject and episode identities stay together across repeats. The first pack is a
development fixture set. An independent held-out evaluation receives a separately
authored pack and split. The designed distribution supports harness correctness;
population prevalence, causal effects, and demographic fairness receive their own
study designs and accountable review.

The pack records an empty planned cohort and a minimum of three independent
subjects for subgroup display. Comparative owns score disclosure, denominators,
and subject-weighted summaries. Scoring a caller's observations preserves changed
scientific outcomes as findings for review.

## Next useful actions

Pass the pack to [Comparative #41](https://github.com/driftframestudios/lims-eln-comparative-evidence/issues/41)
for substantive scoring. [Enterprise #36](https://github.com/driftframestudios/lims-eln-enterprise-implementation/issues/36)
owns source-adapter execution, while [#39](https://github.com/driftframestudios/lims-eln-simulated-final-state/issues/39)
receives the exercised authoring and recovery procedure. Tags, public projection,
and external model execution retain explicit release decisions.

Return to the [repository quick start](../README.md#start-with-one-scenario).

## Source admission and recovery

The installed `cases.v1.json` resource owns this pack's records and independent
expected results. Admission binds the source, policy, vocabulary, scoring
coordinate, planned runs, paired expectations, and oracle rows to that resource.
Paired arms and repeated subject/episode units retain the same cohort identity.
The four bounded repeat configurations use immutable process-local projections.
A reviewed source revision receives a new version and a fresh process.

A receiving study can declare another expected execution identity or raise its
minimum paired-subject threshold. These choices preserve the authored matrix.
Teams developing another matrix can use the fixture and typed model as a design
example, then review a distinct source version with its own expected results.

`pack_administrative_input` routes malformed administrative JSON to the finite
input contract: an exact raw label, calendar day, enrollment, review, and
reportability. `pack_source_binding` routes a changed source or oracle back to
its reviewed resource. Regenerate the pack from that resource and retain the
original observation document for comparison.

## Complete file publication and retry

The CLI admits the full pack before writing. It writes a private temporary file
inside the destination directory, completes and synchronizes those bytes, then
creates the final name with an exclusive hard link and synchronizes the directory.
Existing files, directories, and symlinks retain their content. Choose a concrete
caller-owned parent directory whose write permissions belong to that caller.
Its ancestor path and same-account writers remain within the caller's trust boundary.

`output_collision` asks for a fresh output name. `output_io` permits a retry after
destination access or capacity is restored. `output_uncertain` means a complete
final file became visible before acknowledgment: inspect it through `admit_pack`,
compare its bytes with the intended pack, and retain it while deciding the next
destination. That observation establishes complete content; filesystem durability
still follows the storage owner's guarantees.

The supported route uses POSIX directory descriptors, hard links, and `fsync`.
`output_platform` asks the caller to select that filesystem capability. Handled
interruption releases the invocation's temporary file. Abrupt process termination
or power loss may retain a `.pack-pending-*` file; the next run uses its own fresh
temporary name. After confirming the producing process has stopped, the owner may
remove that exact orphan. Keep other invocations' temporary files in place.

Run the focused output and pack checks with the administrative profile:

```bash
PYTHONPATH=src .venv-admin/bin/python -m unittest discover -s tests -p 'test_atomic_output.py' -v
PYTHONPATH=src .venv-admin/bin/python -m unittest discover -s tests -p 'test_administrative_pack.py' -v
```

The implementation follows Python's [descriptor-relative file operations](https://docs.python.org/3.12/library/os.html#os.link)
and [signal masking](https://docs.python.org/3.12/library/signal.html#signal.pthread_sigmask).
These checks establish complete visibility, exclusive publication, and owned
recovery on the exercised filesystem; broader storage guarantees retain their
configured evidence route.
