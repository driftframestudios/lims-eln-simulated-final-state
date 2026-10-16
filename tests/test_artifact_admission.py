"""Native representation limits precede content work and preserve recovery."""

from copy import deepcopy
from hashlib import sha256
import io
import json
import os
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "src"), str(ROOT / "infra")]
from lims_eln_sim import artifact_boundary as boundary
from container_entry import produce
from container_runtime import publish


ARTIFACT_NAMES = (
    "acceptance-drafts.json", "bounded-caller.json", "future-reality-closure-bundle.json",
    "migration-report.json", "observation-envelope.json", "receipt-closure-summary.json",
    "restore-report.json", "result.json", "scenario-execution.json", "security-exercise.json",
    "simulated-receipt-closure.json", "simulated-receipts.json", "telemetry-summary.json",
)
FILE_BYTES = 4 * 1024 * 1024
FAMILY_BYTES = 32 * 1024 * 1024


class ArtifactAdmissionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            produce(root)
            cls.generated = {path.name: path.read_bytes() for path in root.iterdir()}

    def setUp(self):
        self.root = Path(self.enterContext(tempfile.TemporaryDirectory()))
        self.write_family(self.root)

    def write_family(self, root):
        for name, content in self.generated.items():
            (root / name).write_bytes(content)

    def expected_inventory(self, root):
        return {name: "sha256:" + sha256((root / name).read_bytes()).hexdigest()
                for name in ARTIFACT_NAMES}

    def test_generated_family_and_literal_policy(self):
        self.assertEqual(set(ARTIFACT_NAMES), set(self.generated))
        self.assertEqual(FILE_BYTES, boundary.MAX_ARTIFACT_BYTES)
        self.assertEqual(FAMILY_BYTES, boundary.MAX_TOTAL_ARTIFACT_BYTES)
        self.assertEqual(32, boundary.MAX_ARTIFACT_JSON_DEPTH)
        self.assertEqual(self.expected_inventory(self.root), boundary.artifact_inventory(self.root))

    def test_family_admission_precedes_reads_decoding_and_hashing(self):
        for kind in ("json", "text", "subtree", "empty_directory", "missing", "named_directory"):
            with self.subTest(kind=kind), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                self.write_family(root)
                if kind == "missing":
                    (root / "result.json").unlink()
                elif kind == "named_directory":
                    (root / "result.json").unlink()
                    (root / "result.json").mkdir()
                elif kind in {"subtree", "empty_directory"}:
                    (root / "unexpected").mkdir()
                    if kind == "subtree":
                        (root / "unexpected" / "data.json").write_bytes(b"{}")
                else:
                    (root / ("unexpected." + kind)).write_bytes(b'"' + b"x" * 1024 + b'"')
                before = {str(p.relative_to(root)): p.read_bytes()
                          for p in root.rglob("*") if p.is_file()}
                with patch.object(boundary, "_read_regular_file") as read, \
                     patch.object(boundary, "strict_json_loads") as decode, \
                     patch.object(boundary, "sha256") as hashed, \
                     patch.object(Path, "rglob", side_effect=AssertionError("recursive enumeration")):
                    with self.assertRaises(boundary.ArtifactBoundaryError):
                        boundary.artifact_inventory(root)
                read.assert_not_called()
                decode.assert_not_called()
                hashed.assert_not_called()
                self.assertEqual(before, {str(p.relative_to(root)): p.read_bytes()
                                          for p in root.rglob("*") if p.is_file()})

    def test_iteration_stops_at_first_unsupported_root_member(self):
        visited = []
        class Entries:
            def __enter__(self):
                return self
            def __exit__(self, *_):
                visited.append("closed")
            def __iter__(self):
                yield SimpleNamespace(name="unexpected.json")
                raise AssertionError("continued beyond rejected member")
        with patch.object(boundary.os, "scandir", return_value=Entries()):
            with self.assertRaisesRegex(boundary.ArtifactBoundaryError, "unexpected"):
                boundary.artifact_inventory(self.root)
        self.assertEqual(["closed"], visited)

    def test_exact_file_limit_and_one_over_before_decoding(self):
        target = self.root / ARTIFACT_NAMES[0]
        content = target.read_bytes()
        target.write_bytes(content + b" " * (FILE_BYTES - len(content)))
        self.assertEqual(self.expected_inventory(self.root), boundary.artifact_inventory(self.root))
        with target.open("ab") as stream:
            stream.write(b" ")
        with patch.object(boundary, "strict_json_loads") as decode, \
             patch.object(boundary, "sha256") as hashed, \
             patch.object(boundary.io, "BufferedReader") as reader:
            with self.assertRaisesRegex(boundary.ArtifactBoundaryError, "4194304 bytes"):
                boundary.artifact_inventory(self.root)
        decode.assert_not_called()
        hashed.assert_not_called()
        reader.assert_not_called()

    def test_enumeration_failure_preserves_cause_control_and_scope(self):
        for stage in ("acquisition", "iteration"):
            for exception_type in (PermissionError, OSError, KeyboardInterrupt, SystemExit):
                with self.subTest(stage=stage, exception=exception_type):
                    failure = exception_type("local enumeration detail")
                    closed = []
                    class Entries:
                        def __enter__(self):
                            return self
                        def __exit__(self, *_):
                            closed.append(True)
                        def __iter__(self):
                            yield SimpleNamespace(
                                name=ARTIFACT_NAMES[0], is_symlink=lambda: False,
                                is_dir=lambda **_: False,
                            )
                            raise failure
                    scan = {"side_effect": failure} if stage == "acquisition" else {"return_value": Entries()}
                    expected = boundary.ArtifactBoundaryError if isinstance(failure, OSError) else exception_type
                    with patch.object(boundary.os, "scandir", **scan), \
                         patch.object(boundary, "_read_regular_file") as read:
                        with self.assertRaises(expected) as caught:
                            boundary.artifact_inventory(self.root)
                    read.assert_not_called()
                    self.assertEqual([] if stage == "acquisition" else [True], closed)
                    if isinstance(failure, OSError):
                        self.assertEqual("artifact root requires readable released-family membership", str(caught.exception))
                        self.assertIs(failure, caught.exception.__cause__)
                    else:
                        self.assertIs(failure, caught.exception)

    def test_read_cap_holds_when_metadata_understates_the_file(self):
        target = self.root / ARTIFACT_NAMES[0]
        target.write_bytes(b" " * (FILE_BYTES + 1))
        fstat = os.fstat
        requests, lengths = [], []
        class ObservedReader(io.BufferedReader):
            def read(reader, size=-1):
                requests.append(size)
                content = super().read(size)
                lengths.append(len(content))
                return content
        def understated(descriptor):
            return SimpleNamespace(st_mode=fstat(descriptor).st_mode, st_size=0)
        with patch.object(boundary.os, "fstat", side_effect=understated), \
             patch.object(boundary.io, "BufferedReader", ObservedReader), \
             patch.object(boundary, "strict_json_loads") as decode, \
             patch.object(boundary, "sha256") as hashed:
            with self.assertRaises(boundary.ArtifactBoundaryError):
                boundary.artifact_inventory(self.root)
        self.assertEqual([FILE_BYTES + 1], requests)
        self.assertEqual([FILE_BYTES + 1], lengths)
        decode.assert_not_called()
        hashed.assert_not_called()

    def test_capacity_rejection_preserves_numeric_cleanup_observation(self):
        target = self.root / ARTIFACT_NAMES[0]
        target.write_bytes(b" " * (FILE_BYTES + 1))
        cleanup = KeyboardInterrupt()
        closed = []
        close = os.close
        def close_then_interrupt(descriptor):
            close(descriptor)
            closed.append(descriptor)
            raise cleanup
        with patch.object(boundary.os, "close", side_effect=close_then_interrupt):
            with self.assertRaises(boundary.ArtifactBoundaryError) as caught:
                boundary.artifact_inventory(self.root)
        self.assertIs(cleanup, caught.exception.cleanup_error)
        self.assertEqual(1, len(closed))
        with self.assertRaises(OSError):
            os.fstat(closed[0])
        self.assertEqual(FILE_BYTES + 1, target.stat().st_size)

    def test_exact_family_limit_and_one_over_use_remaining_bytes(self):
        padding = FAMILY_BYTES - sum(len(content) for content in self.generated.values())
        for name in ARTIFACT_NAMES:
            content = self.generated[name]
            extra = min(padding, FILE_BYTES - len(content))
            (self.root / name).write_bytes(content + b" " * extra)
            padding -= extra
        self.assertEqual(0, padding)
        self.assertEqual(FAMILY_BYTES, sum(p.stat().st_size for p in self.root.iterdir()))
        self.assertEqual(self.expected_inventory(self.root), boundary.artifact_inventory(self.root))
        last = self.root / ARTIFACT_NAMES[-1]
        last_bytes = last.stat().st_size
        with last.open("ab") as stream:
            stream.write(b" ")
        # A false size observation still leaves the bounded read authoritative.
        fstat = os.fstat
        requests = []
        class ObservedReader(io.BufferedReader):
            def read(reader, size=-1):
                requests.append(size)
                return super().read(size)
        def understated(descriptor):
            return SimpleNamespace(st_mode=fstat(descriptor).st_mode, st_size=0)
        decode, hashed = boundary.strict_json_loads, boundary.sha256
        with patch.object(boundary.os, "fstat", side_effect=understated), \
             patch.object(boundary.io, "BufferedReader", ObservedReader), \
             patch.object(boundary, "strict_json_loads", wraps=decode) as decoded, \
             patch.object(boundary, "sha256", wraps=hashed) as hashes:
            with self.assertRaises(boundary.ArtifactBoundaryError):
                boundary.artifact_inventory(self.root)
        self.assertEqual(last_bytes + 1, requests[-1])
        self.assertEqual(12, decoded.call_count)
        self.assertEqual(12, hashes.call_count)

    def test_depth_limits_and_json_encodings_preserve_string_meaning(self):
        result = json.loads(self.generated["result.json"])
        original = deepcopy(result)
        text = 'quoted " and slash \\ with [{]} ' + "\u2200\u5b00\u5d00\u7b00\u7d00"
        for encoding in ("utf-8", "utf-8-sig", "utf-16", "utf-16-le", "utf-16-be",
                         "utf-32", "utf-32-le", "utf-32-be"):
            for depth in (32, 33):
                with self.subTest(encoding=encoding, depth=depth):
                    value = text
                    for _ in range(depth - 1):
                        value = [value]
                    candidate = deepcopy(result)
                    candidate["admission_probe"] = value
                    content = json.dumps(candidate, ensure_ascii=False).encode(encoding)
                    (self.root / "result.json").write_bytes(content)
                    if depth == 32:
                        self.assertEqual(self.expected_inventory(self.root), boundary.artifact_inventory(self.root))
                    else:
                        decode = boundary.strict_json_loads
                        with patch.object(boundary, "strict_json_loads", wraps=decode) as decoded, \
                             patch.object(boundary, "_validate_document_links") as linked:
                            with self.assertRaisesRegex(boundary.ArtifactBoundaryError, "32 nested containers"):
                                boundary.artifact_inventory(self.root)
                        self.assertFalse(any("admission_probe" in call.args[0] for call in decoded.call_args_list))
                        linked.assert_not_called()
        self.assertEqual(original, result)

    def test_observation_encoding_remains_independent_of_result_encoding(self):
        text = self.generated["observation-envelope.json"].decode("utf-8")
        for encoding in ("utf-8-sig", "utf-16", "utf-16-be", "utf-32", "utf-32-be"):
            with self.subTest(encoding=encoding):
                (self.root / "observation-envelope.json").write_bytes(text.encode(encoding))
                self.assertEqual(self.expected_inventory(self.root), boundary.artifact_inventory(self.root))

    @staticmethod
    def write_deep_family(root):
        deep = b"[" * 1100 + b"0" + b"]" * 1100
        for name in ARTIFACT_NAMES:
            (root / name).write_bytes(b"null")
        (root / "observation-envelope.json").write_bytes(deep)
        (root / "result.json").write_bytes(b'{"observation":' + deep + b'}')

    def test_deep_linked_values_stop_before_decode_or_recursive_comparison(self):
        self.write_deep_family(self.root)
        decode = boundary.strict_json_loads
        with patch.object(boundary, "strict_json_loads", wraps=decode) as decoded, \
             patch.object(boundary, "_validate_document_links") as linked:
            with self.assertRaisesRegex(boundary.ArtifactBoundaryError, "32 nested containers"):
                boundary.artifact_inventory(self.root)
        self.assertTrue(all(call.args[0] == "null" for call in decoded.call_args_list))
        linked.assert_not_called()

    def test_strict_json_keeps_duplicate_nonfinite_unicode_and_syntax_errors(self):
        for content in (b'{"x":1,"x":2}', b'NaN', b'Infinity', b'-1e400',
                        b'"\xff"', b'"\\uZZZZ"', b'"unterminated', b'][{}]'):
            with self.subTest(content=content):
                (self.root / ARTIFACT_NAMES[0]).write_bytes(content)
                with self.assertRaisesRegex(boundary.ArtifactBoundaryError, "strict JSON"):
                    boundary.artifact_inventory(self.root)

    def test_supported_scalar_projections_keep_json_meaning(self):
        for value in (None, True, 0, 1.25, "brackets []{} and Unicode \u2200"):
            with self.subTest(value=value):
                result = json.loads(self.generated["result.json"])
                result["acceptance_drafts"] = value
                (self.root / "result.json").write_text(json.dumps(result), encoding="utf-8")
                (self.root / "acceptance-drafts.json").write_text(json.dumps(value), encoding="utf-8")
                self.assertEqual(self.expected_inventory(self.root), boundary.artifact_inventory(self.root))

    def test_owned_programming_error_retains_its_identity(self):
        failure = TypeError("owned calculation failure")
        with patch.object(boundary, "strict_json_loads", side_effect=failure):
            with self.assertRaises(TypeError) as caught:
                boundary.artifact_inventory(self.root)
        self.assertIs(failure, caught.exception)

    def test_actual_publisher_preserves_prior_run_and_accepts_corrected_retry(self):
        for fault in ("membership", "bytes", "depth"):
            with self.subTest(fault=fault), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                first = publish(produce, root, validate=boundary.artifact_inventory)
                accepted = root / first["directory"]
                saved = {str(p.relative_to(accepted)): p.read_bytes()
                         for p in accepted.rglob("*") if p.is_file()}
                def candidate(payload):
                    produce(payload)
                    if fault == "membership":
                        (payload / "unexpected.json").write_bytes(b"{}")
                    elif fault == "bytes":
                        (payload / ARTIFACT_NAMES[0]).write_bytes(b" " * (FILE_BYTES + 1))
                    else:
                        self.write_deep_family(payload)
                with self.assertRaises(boundary.ArtifactBoundaryError):
                    publish(candidate, root, validate=boundary.artifact_inventory)
                self.assertEqual([accepted], list(root.iterdir()))
                self.assertEqual(saved, {str(p.relative_to(accepted)): p.read_bytes()
                                         for p in accepted.rglob("*") if p.is_file()})
                retry = publish(produce, root, validate=boundary.artifact_inventory)
                self.assertNotEqual(first["directory"], retry["directory"])
                self.assertEqual(boundary.artifact_inventory(accepted / "payload"),
                                 boundary.artifact_inventory(root / retry["directory"] / "payload"))


if __name__ == "__main__":
    unittest.main()
