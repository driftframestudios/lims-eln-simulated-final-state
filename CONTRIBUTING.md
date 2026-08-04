# Contributing

Start work from `develop` using `feature/<issue>-<slug>`. Merge through a reviewed
pull request after the focused vendor-evaluation tests pass. Release and hotfix
branches follow the repository's GitFlow-like convention.

GitHub branch protection, required checks, and CODEOWNERS implement branch
policy. Dependabot updates GitHub Actions monthly and follows the same tests and
review path.

Each change should preserve these qualities:

1. Inputs remain synthetic and reproducible.
2. Vendor behavior is explicit and versioned.
3. Migration, restore, and data-exit comparisons preserve scientific meaning.
4. AWS configuration output contains references and versions while resolved values stay private.
5. The runtime emits one portable advisory result with `runtime_effect: none`.
6. Historical control-plane material stays under `reference/quarantine/`.
