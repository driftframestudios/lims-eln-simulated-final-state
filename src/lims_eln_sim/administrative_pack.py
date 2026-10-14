"""Owned synthetic plans and independent oracles for administrative comparisons.

Generation traverses the bounded case/cohort/repeat product once, O(R + B)
time and space for emitted runs R and serialized bytes B. Admission indexes
oracles once, O(R + B), plus the Program model's bounded relationship checks.
The package retains immutable values; returned JSON projections are detached.
"""

from __future__ import annotations

import argparse
from datetime import date
from functools import lru_cache
from importlib.resources import files
import json
from pathlib import Path
import signal
from typing import Annotated, Literal, Self

from pydantic import Field, ValidationError, model_validator
from lims_eln_contracts.administrative_study import AdministrativeStudy, admit_administrative_study
from lims_eln_contracts.canonical import canonical_json_bytes, canonical_sha256, strict_json_loads
from lims_eln_contracts.primitives import ContractModel, Identifier, Sha256Digest
from lims_eln_contracts.resources import load_administrative_study_example

from .safety import SECRET_PATTERNS
from .atomic_output import OutputPublicationError, OutputPublicationInterrupted, publish_file

PROGRAM_SOURCE = "83a97deb76b9a5636cc7da484d350d5556c51661"
PACK_SCHEMA = "urn:driftframe:simulation:administrative-pack:1.0.0"
MAX_BYTES = 2_097_152
Token = Annotated[str, Field(pattern=r"^SYN-[A-Za-z0-9-]{1,80}$")]
Tokens = Annotated[tuple[Token, ...], Field(max_length=16)]
Classification = Literal["matched", "multiple", "ambiguous", "unknown", "absent", "abstain"]
PolicyState = Literal["review", "submit", "conflict", "pending", "expired", "overridden", "retracted"]


class PackBoundaryError(ValueError):
    """A fixed public code keeps rejected source material with its caller."""

    def __init__(self, code: str):
        self.code = code
        super().__init__(code + ": use the versioned synthetic pack and its declared bounds")


class AdministrativeInput(ContractModel):
    raw_label: Annotated[str, Field(max_length=1024)]
    service_day: Annotated[str, Field(pattern=r"^[0-9]{4}-[0-9]{2}-[0-9]{2}$")]
    enrollment: Literal["active", "pending"]
    review: Literal["source", "accepted-employer", "retracted"]
    reportability: Literal["category", "reportable"]

    @model_validator(mode="after")
    def calendar_day(self) -> Self:
        date.fromisoformat(self.service_day)
        return self


def admit_administrative_input(text: str) -> AdministrativeInput:
    """Admit the finite consumer shape while preserving the original label."""
    try:
        strict_json_loads(text)
        return AdministrativeInput.model_validate_json(text, strict=True)
    except (ValueError, TypeError, RecursionError):
        raise PackBoundaryError("pack_administrative_input") from None


class ExpectedResult(ContractModel):
    run_id: Token
    case_id: Token
    cohort: Token
    family: Literal["administrative_context", "demographic_presentation", "control"]
    labels: Tokens
    classification: Classification
    policy_state: PolicyState
    required_facts: Tokens
    allowed_facts: Tokens
    workflow_minutes: Annotated[int, Field(ge=0, le=1440)]
    expected_status: Literal["completed", "abstained", "failed", "pending", "excluded"] = "completed"

    @model_validator(mode="after")
    def exact_sets(self) -> Self:
        for values in (self.labels, self.required_facts, self.allowed_facts):
            if len(values) != len(set(values)):
                raise ValueError("expected sets retain unique terms")
        if not set(self.required_facts) <= set(self.allowed_facts):
            raise ValueError("required facts resolve within allowed evidence")
        return self


class PackDesign(ContractModel):
    construction: Literal["authored_synthetic_factor_matrix"] = "authored_synthetic_factor_matrix"
    seed: Literal[0] = 0
    generator_version: Literal["1.0.0"] = "1.0.0"
    experimental_unit: Literal["subject_episode"] = "subject_episode"
    split: Literal["harness_development"] = "harness_development"
    planned_cohorts: Annotated[tuple[Token, ...], Field(min_length=1, max_length=8)]
    minimum_subjects: Annotated[int, Field(ge=2, le=32)] = 3
    repeats: Annotated[int, Field(ge=1, le=4)]
    source_digest: Sha256Digest
    evidence_scope: Literal["authored_harness_correctness"] = "authored_harness_correctness"


class ScenarioPack(ContractModel):
    schema_id: Literal[PACK_SCHEMA] = Field(alias="$schema")
    program_version: Literal["0.6.1"] = "0.6.1"
    program_source: Literal[PROGRAM_SOURCE] = PROGRAM_SOURCE
    design: PackDesign
    study: AdministrativeStudy
    expected: Annotated[tuple[ExpectedResult, ...], Field(min_length=2, max_length=512)]

    @model_validator(mode="after")
    def bind_expectations(self) -> Self:
        runs = {run.run_id: run for run in self.study.runs}
        expected = {item.run_id: item for item in self.expected}
        if len(expected) != len(self.expected) or set(expected) != set(runs):
            raise ValueError("independent expectations cover each planned run exactly once")
        if self.study.observations:
            raise ValueError("pack plans carry expectations; observation documents are separate")
        cohorts = set(self.design.planned_cohorts)
        if len(cohorts) != len(self.design.planned_cohorts):
            raise ValueError("planned cohort identities are unique")
        pair_cohorts = {}
        unit_cohorts = {}
        for run in runs.values():
            if any(not identity.startswith("SYN-") for identity in (run.run_id, run.pair_id, run.scenario_id, run.subject_id, run.episode_id)):
                raise ValueError("generated identities occupy the SYN namespace")
            if expected[run.run_id].cohort not in cohorts:
                raise ValueError("expected cohorts resolve to the planned matrix")
            oracle = expected[run.run_id]
            if oracle.case_id != run.scenario_id:
                raise ValueError("expected case identity matches its planned scenario")
            pair_cohort = pair_cohorts.setdefault(run.pair_id, oracle.cohort)
            unit_cohort = unit_cohorts.setdefault((run.subject_id, run.episode_id), oracle.cohort)
            if oracle.cohort != pair_cohort or oracle.cohort != unit_cohort:
                raise ValueError("paired arms and repeated experimental units share one cohort")
        return self


def admit_pack(payload: bytes) -> ScenarioPack:
    """Admit bounded, strict UTF-8 JSON and the authoritative Program study."""
    if type(payload) is not bytes or len(payload) > MAX_BYTES:
        raise PackBoundaryError("pack_bytes")
    try:
        text = payload.decode("utf-8")
        if any(pattern.search(text) for pattern in SECRET_PATTERNS):
            raise PackBoundaryError("pack_source_review")
        document = strict_json_loads(text)
        pack = ScenarioPack.model_validate_json(text, strict=True)
        admit_administrative_study(canonical_json_bytes(document["study"]))
        for run in pack.study.runs:
            admit_administrative_input(run.administrative_input)
        _bind_owned_source(pack)
        return pack
    except PackBoundaryError:
        raise
    except (ValueError, TypeError, KeyError, RecursionError):
        raise PackBoundaryError("pack_contract") from None


@lru_cache(maxsize=4)
def _owned_pack_bytes(repeats: int) -> bytes:
    """Retain immutable source projections for the four declared repeat counts."""
    source = strict_json_loads(files("lims_eln_sim").joinpath("administrative_resources/cases.v1.json").read_bytes())
    seed = load_administrative_study_example().model_dump(mode="json", by_alias=True)
    spec = seed["specification"]
    source_digest = canonical_sha256(source)
    spec.update(study_id="SYN-ADMINISTRATIVE-PACK", version="1.0.0", question="Which declared administrative changes preserve source evidence and alter workflow?", requested_return="Score independent expected fields, retain each planned run, and identify the next review.", primary_endpoint="Exact normalized label-set agreement among usable runs", controlled_factors=[], factor_names=["age_band", "language", "reportability"], stopping_rule="Complete the declared finite matrix; retain each incomplete outcome.", max_attempts_per_run=2)
    spec["source"] = {"data_class":"synthetic", "construction":"authored_fixture", "artifact":{"artifact_id":"SYN-ADMINISTRATIVE-CASES", "version":"1.0.0", "digest":source_digest}, "review_ref":"simulation-issue-38", "purpose":"Exercise a designed fixture distribution and independent expected outcomes."}
    spec["catalog"] = {"artifact_id":"SYN-INSURANCE-CATALOG", "version":"1.0.0", "digest":canonical_sha256(source["vocabulary"])}
    spec["policy"] = {"artifact_id":"SYN-ADMINISTRATIVE-RULES", "version":"1.0.0", "digest":canonical_sha256(source["policy"])}
    spec["scoring"] = {"artifact_id":"SYN-ADMINISTRATIVE-SCORING", "version":"1.0.0", "digest":canonical_sha256(source["scoring"])}
    spec["expected_execution"] = {"provider_id":"SYN-OFFLINE", "model_id":"SYN-RESPONSE-FIXTURE", "adapter_version":"1.0.0", "prompt_digest":canonical_sha256("Preserve the supplied facts and return the declared administrative fields."), "configuration_digest":canonical_sha256({"order":"counterbalanced", "repeats":repeats})}
    runs, expected, pairs = [], [], []
    for case in source["cases"]:
        for group in source["cohorts"]:
            subject = "SYN-SUBJECT-" + case["id"] + "-" + group["id"]
            for repeat in range(repeats):
                pair = "SYN-PAIR-" + case["id"] + "-" + group["id"] + "-" + str(repeat)
                for arm in ("a", "b"):
                    value = case[arm]
                    run_id = pair + "-" + arm
                    language = value.get("language", group["language"])
                    runs.append({"run_id":run_id, "pair_id":pair, "arm":arm, "scenario_id":"SYN-CASE-" + case["id"], "subject_id":subject, "episode_id":subject + "-EPISODE", "repeat_index":repeat, "scientific_evidence":source["scientific_evidence"], "administrative_input":canonical_json_bytes({"raw_label":value["raw_label"], "service_day":value.get("service_day", "2026-10-14"), "enrollment":value.get("enrollment", "active"), "review":value.get("review", "source"), "reportability":value.get("reportability", "category")}).decode(), "factors":[{"name":"age_band","standing":"specified","value":group["age_band"]},{"name":"language","standing":"specified","value":language},{"name":"reportability","standing":"specified","value":value.get("reportability","category")}]})
                    expected.append({"run_id":run_id, "case_id":"SYN-CASE-" + case["id"], "cohort":"SYN-COHORT-" + group["id"], "family":case["family"], "labels":value["labels"], "classification":value["classification"], "policy_state":value["policy_state"], "required_facts":source["required_facts"], "allowed_facts":source["required_facts"], "workflow_minutes":value["workflow_minutes"], "expected_status":value.get("status","completed")})
                pairs.append({"pair_id":pair, "scientific_changed":False, "administrative_changed":case["expected_administrative_change"], "rationale":case["rationale"]})
    pack = {"$schema":PACK_SCHEMA, "program_version":"0.6.1", "program_source":PROGRAM_SOURCE, "design":{"planned_cohorts":["SYN-COHORT-" + group["id"] for group in source["cohorts"]] + ["SYN-COHORT-UNREPRESENTED"], "repeats":repeats,"source_digest":source_digest}, "study":{"$schema":seed["$schema"], "specification":spec, "runs":runs,"observations":[], "expected_pairs":pairs}, "expected":expected}
    return canonical_json_bytes(pack)


def _bind_owned_source(pack: ScenarioPack) -> None:
    """Bind owned claims to packaged source; preserve declared receiver choices."""
    reference = strict_json_loads(_owned_pack_bytes(pack.design.repeats))
    source_study = admit_administrative_study(canonical_json_bytes(reference["study"]))
    actual_spec = pack.study.specification.model_dump(mode="json")
    source_spec = source_study.specification.model_dump(mode="json")
    # The receiver can request another producer while the authored matrix stays owned.
    actual_spec.pop("expected_execution")
    source_spec.pop("expected_execution")
    same_source = (
        pack.design.source_digest == reference["design"]["source_digest"]
        and set(pack.design.planned_cohorts) == set(reference["design"]["planned_cohorts"])
        and actual_spec == source_spec
        and {run.run_id: run for run in pack.study.runs} == {run.run_id: run for run in source_study.runs}
        and {pair.pair_id: pair for pair in pack.study.expected_pairs} == {pair.pair_id: pair for pair in source_study.expected_pairs}
        and {row.run_id: row.model_dump(mode="json") for row in pack.expected} == {row["run_id"]: row for row in reference["expected"]}
    )
    if not same_source:
        raise PackBoundaryError("pack_source_binding")


def build_pack(*, repeats: int = 2) -> ScenarioPack:
    """Build the declared matrix in stable case/cohort/repeat/arm order."""
    if type(repeats) is not int or not 1 <= repeats <= 4:
        raise PackBoundaryError("repeat_budget")
    return admit_pack(_owned_pack_bytes(repeats))


def main() -> None:
    parser = argparse.ArgumentParser(description="Write one versioned synthetic scenario pack.")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--repeats", type=int, default=2)
    args = parser.parse_args()
    def interrupted(number, _frame):
        raise SystemExit(128 + number)
    previous = signal.signal(signal.SIGTERM, interrupted)
    try:
        payload = canonical_json_bytes(build_pack(repeats=args.repeats)) + b"\n"
        admit_pack(payload)
        args.output.parent.mkdir(parents=True, exist_ok=True)
        publish_file(args.output, payload)
    except OutputPublicationInterrupted as error:
        parser.exit(error.code, error.recovery + "\n")
    except (PackBoundaryError, OutputPublicationError) as error:
        parser.exit(2, str(error) + "\n")
    except OSError:
        parser.exit(2, "output_destination: prepare a writable caller-owned output directory.\n")
    finally:
        signal.signal(signal.SIGTERM, previous)


if __name__ == "__main__":
    main()
