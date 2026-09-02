---
name: contextual-jargon-scan
description: Classifies specialist and collaboration-local wording in a bounded Simulation corpus and revises replaceable shorthand into ordinary language. Applies in stride when public guidance, selected-future orientation, release prose, or cross-repository instructions may assume context the reader does not share.
source_band: public_possible
skill_version: 0.1.0
upstream_repository: driftframestudios/human-ai-systems-exemplars
upstream_path: .agents/skills/contextual-jargon-scan/SKILL.md
upstream_revision: 0c023343e46cd9b1333a63c2d509787352fbad14
upstream_blob_sha1: 3c3a94db99152385253e0281c8afa8fea8208ac5
upstream_sha256: da383f99eaff364d7e17c3bff93d8da618ec95894a45ff78a9620d8d7fc81523
adaptation_relation: repository_local_derivative
---

# Simulation contextual jargon scan

## Contract

- **What:** A context-aware review that distinguishes exact Simulation and
  engineering language from shorthand a reader must decode.
- **When:** A bounded public, cross-repository, selected-future orientation,
  release, or instruction surface is already receiving material prose changes.
- **Boundaries:** Schema keys, identifiers, version coordinates, code,
  quotations, citations, accessibility meaning, established technical terms,
  and source-owned language retain their fidelity. Search tools produce
  candidates; contextual reading determines whether a change helps. The scan
  remains within the active corpus.
- **Result:** A scoped occurrence map, targeted revisions, intentional
  retentions that affect future work, and a verification signal tied to the
  changed prose.

## Rules

### Rule: Scope and reader come first

Name the files already changing, the downstream engineer, reviewer,
comparator, evaluator, or public reader they serve, and any exclusions. A
focused scan follows the active task. Repository-wide wording work receives
its own scope and reader.

### Rule: Search results are candidates

Search relevant word families with surrounding context. Counts help locate
repetition and variation; they neither prove a defect nor define completion.

### Rule: Each material occurrence receives a functional class

Classify an occurrence as:

1. literal ordinary language;
2. an exact technical, schema, release, scientific, or governed term;
3. quoted, cited, or source-owned language;
4. useful compact language whose relationship is locally retrievable; or
5. replaceable shorthand that asks the reader to infer a local object, action,
   boundary, or consequence.

The same word can carry several classes in one document.

### Rule: Exact contract language stays exact

Preserve keys such as `evidence_mode`, `assurance_stage`, stable identifiers,
Git object names, SHA-256 coordinates, schema versions, evidence stages, and
release tags. Explain their role nearby when the receiving reader needs that
context.

### Rule: Simulation names earn a direct first use

Terms such as selected future, counterfactual, Machine Node, First Receipt,
Coordination Horizon, canonical closure, and bounded caller can remain when
they improve retrieval. Near first use, state the ordinary reader job or
relationship they name.

### Rule: Replacement follows function

For replaceable shorthand, name the concrete source, action, relation,
authority boundary, evidence state, or consequence it was carrying. Prefer the
smallest revision that preserves technical depth and the document's voice.

### Rule: Tooling remains advisory

`rg`, occurrence inventories, and deterministic checks can surface review
candidates. A passing tool establishes its named policy only; paragraph-level
reading establishes whether a reader can retrieve the intended meaning.

## Operating sequence

1. **Bind the review:** Name corpus, reader, active change, exclusions, and
   candidate word families.
2. **Gather occurrences:** Search each family with enough context to read its
   actual role.
3. **Classify:** Mark material uses as literal, exact, source-owned, useful
   compact language, or replaceable shorthand.
4. **Choose the smallest action:** Retain, define, revise, or defer each
   decision-changing occurrence.
5. **Revise in context:** Use concrete nouns, verbs, relations, and evidence
   consequences.
6. **Reconcile nearby carriers:** Inspect headings, links, metadata, schema
   descriptions, repeated definitions, and comparison language that share the
   same reader job.
7. **Verify:** Re-read each changed passage, rescan the bounded corpus, and run
   the receiving structural checks.
8. **Return:** Name scope, material revisions, intentional retentions, exact
   validation, coverage boundary, and any next receiver.

## Output shape

```text
Corpus and reader:
Exclusions:
Candidate families:
Revised shorthand:
Retained exact or useful terms:
Reader verification:
Structural verification:
Deferred receiver, if any:
```

## Representative scenario

### Scenario: One Simulation term is exact and another use is opaque

Given `Coordination Horizon` names the validated current-work and re-entry
record in one passage<br>
And `horizon` loosely stands for an unspecified future plan elsewhere<br>
When the two occurrences are classified<br>
Then the exact record name remains with its reader job nearby<br>
And the loose occurrence names the specific future decision or time boundary
it carries<br>
And completion depends on reader legibility rather than eliminating the word

## Adaptation lineage

This repository-local derivative narrows a shared contextual-jargon method to
Simulation prose, selected-future orientation, release records,
cross-repository instructions, and comparison language. Its upstream revision
and content identities preserve the selected source while this copy remains
independently usable.

## Completion

The scan completes when the bounded reader can retrieve each material object,
action, relation, and consequence; retained specialist language performs an
exact or useful job; prose reading plus repository checks establish the changed
surface; and word counts remain navigation aids rather than acceptance targets.
