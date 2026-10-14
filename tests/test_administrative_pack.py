"""Independent boundaries for the optional administrative-study profile."""
from importlib.util import find_spec
import json
from pathlib import Path
import unittest

HAS_ADMINISTRATIVE_STUDY = (
    find_spec("lims_eln_contracts") is not None
    and find_spec("lims_eln_contracts.administrative_study") is not None
)
if HAS_ADMINISTRATIVE_STUDY:
    from lims_eln_contracts.canonical import canonical_json_bytes
    from lims_eln_contracts.administrative_study import admit_administrative_study
    from lims_eln_sim.administrative_pack import MAX_BYTES, PackBoundaryError, admit_pack, build_pack


@unittest.skipUnless(HAS_ADMINISTRATIVE_STUDY, "administrative-study extra supplies the reviewed Program contract")
class AdministrativePackTests(unittest.TestCase):
    def test_default_matrix_and_program_admission(self):
        pack = build_pack()
        self.assertEqual(144, len(pack.study.runs))
        self.assertEqual(72, len(pack.study.expected_pairs))
        self.assertEqual(144, len(pack.expected))
        self.assertEqual(36, len({r.subject_id for r in pack.study.runs}))
        self.assertEqual(pack.study, admit_administrative_study(canonical_json_bytes(pack.study)))

    def test_bounded_parameterized_repeats_and_deterministic_replay(self):
        for repeats in (1,2,4):
            with self.subTest(repeats=repeats):
                first = canonical_json_bytes(build_pack(repeats=repeats))
                self.assertEqual(first, canonical_json_bytes(build_pack(repeats=repeats)))
                self.assertEqual(72*repeats, len(admit_pack(first).study.runs))
        for value in (0,5,-1,True,1.5,"2"):
            with self.subTest(value=value), self.assertRaises(PackBoundaryError):
                build_pack(repeats=value)

    def test_scientific_pair_invariants_and_raw_preservation(self):
        pack = build_pack(repeats=1)
        pairs = {}
        for run in pack.study.runs:
            pairs.setdefault(run.pair_id,[]).append(run)
        for pair in pairs.values():
            self.assertEqual(pair[0].scientific_evidence,pair[1].scientific_evidence)
            self.assertEqual(pair[0].subject_id,pair[1].subject_id)
            self.assertEqual(pair[0].episode_id,pair[1].episode_id)
        first = pack.study.runs[0]
        self.assertEqual("  Commercial  ",json.loads(first.administrative_input)["raw_label"])

    def test_case_ladder_and_empty_planned_cohort(self):
        pack = build_pack(repeats=1)
        self.assertEqual({"matched","multiple","ambiguous","unknown","absent","abstain"},{row.classification for row in pack.expected})
        self.assertEqual({"completed","failed","pending","excluded","abstained"},{row.expected_status for row in pack.expected})
        self.assertIn("SYN-COHORT-UNREPRESENTED",pack.design.planned_cohorts)
        self.assertEqual({"administrative_context","demographic_presentation","control"},{row.family for row in pack.expected})

    def test_pack_rejects_broken_coverage_and_contracts(self):
        def missing(doc): doc["expected"].pop()
        def duplicate(doc): doc["expected"][1]=doc["expected"][0]
        def foreign(doc): doc["study"]["runs"][0]["subject_id"]="external-person"
        def unknown_cohort(doc): doc["expected"][0]["cohort"]="SYN-UNDECLARED"
        def drift(doc): doc["program_source"]="f"*40
        def surplus(doc): doc["surplus"]=True
        def secret(doc): doc["study"]["runs"][0]["administrative_input"]="ghp_"+"a"*30
        for mutation in (missing,duplicate,foreign,unknown_cohort,drift,surplus,secret):
            with self.subTest(mutation=mutation.__name__):
                doc=build_pack(repeats=1).model_dump(mode="json",by_alias=True)
                mutation(doc)
                with self.assertRaises(PackBoundaryError): admit_pack(canonical_json_bytes(doc))

    def test_json_and_byte_boundaries(self):
        for payload in (b"{"*40,b'{"x":1,"x":2}',b'{"x":NaN}',b"["*2000+b"]"*2000,b"\xff",b" "*(MAX_BYTES+1),"text"):
            with self.subTest(kind=type(payload).__name__),self.assertRaises(PackBoundaryError): admit_pack(payload)

    def test_owned_source_and_oracle_binding(self):
        def oracle(doc): doc["expected"][0]["labels"] = ["SYN-DIFFERENT"]
        def source(doc): doc["design"]["source_digest"] = "sha256:" + "f" * 64
        def artifact(doc): doc["study"]["specification"]["source"]["artifact"]["digest"] = "sha256:" + "f" * 64
        def science(doc): doc["study"]["runs"][0]["scientific_evidence"] = "Another authored source"
        for mutation in (oracle, source, artifact, science):
            with self.subTest(mutation=mutation.__name__):
                document = build_pack(repeats=1).model_dump(mode="json", by_alias=True)
                mutation(document)
                with self.assertRaises(PackBoundaryError) as caught:
                    admit_pack(canonical_json_bytes(document))
                self.assertEqual("pack_source_binding", caught.exception.code)

    def test_cohort_identity_across_arms_and_repeats(self):
        for cross_repeat in (False, True):
            with self.subTest(cross_repeat=cross_repeat):
                document = build_pack(repeats=2).model_dump(mode="json", by_alias=True)
                changed_indices = (2, 3) if cross_repeat else (1,)
                for index in changed_indices:
                    document["expected"][index]["cohort"] = "SYN-COHORT-UNREPRESENTED"
                with self.assertRaises(PackBoundaryError):
                    admit_pack(canonical_json_bytes(document))

    def test_administrative_input_shape_returns_fixed_boundary(self):
        original = json.loads(build_pack(repeats=1).study.runs[0].administrative_input)
        malformed = ("{}", "null", "[]", '{"raw_label":"a","raw_label":"b"}',
                     json.dumps(dict(original, raw_label=4)),
                     json.dumps(dict(original, service_day="2026-02-30")),
                     json.dumps(dict(original, service_day="2026-1-1")),
                     json.dumps(dict(original, enrollment="unreviewed")),
                     json.dumps(dict(original, surplus=True)))
        for text in malformed:
            with self.subTest(text=text):
                document = build_pack(repeats=1).model_dump(mode="json", by_alias=True)
                document["study"]["runs"][0]["administrative_input"] = text
                with self.assertRaises(PackBoundaryError) as caught:
                    admit_pack(canonical_json_bytes(document))
                self.assertEqual("pack_administrative_input", caught.exception.code)

    def test_owned_snapshot(self):
        pack=build_pack(repeats=1)
        document=pack.model_dump(mode="json",by_alias=True)
        document["study"]["runs"][0]["scientific_evidence"]="Changed caller copy"
        self.assertEqual(pack,admit_pack(canonical_json_bytes(pack)))
        self.assertNotEqual(document["study"]["runs"][0]["scientific_evidence"],pack.study.runs[0].scientific_evidence)


class AdministrativeOrientationTests(unittest.TestCase):
    def test_action_precedes_reference_inventory(self):
        root=Path(__file__).resolve().parents[1]
        text=(root/"README.md").read_text()
        self.assertLess(text.index("--output build/first-scenario"),text.index("## Choose a route"))
        for route in ("lims-eln-comparative-evidence/issues/44","lims-eln-program-specification/issues/54","lims-eln-simulated-final-state/issues/39","docs/administrative-scenarios.md"):
            self.assertIn(route,text)
        self.assertTrue((root/"docs/administrative-scenarios.md").is_file())


if __name__ == "__main__": unittest.main()
