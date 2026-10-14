"""Independent byte, ownership and interruption oracles for single-file output."""
from concurrent.futures import ThreadPoolExecutor
import errno
from importlib.util import find_spec
import os
from pathlib import Path
import signal
import stat
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from lims_eln_sim import atomic_output as output

ROOT = Path(__file__).resolve().parents[1]
HAS_ADMINISTRATIVE_STUDY = (
    find_spec("lims_eln_contracts") is not None
    and find_spec("lims_eln_contracts.administrative_study") is not None
)


class AtomicOutputTests(unittest.TestCase):
    def setUp(self):
        self.root = Path(self.enterContext(tempfile.TemporaryDirectory()))
        self.target = self.root / "pack.json"
        self.payload = b'{"fixture":"retained byte meaning"}\n'
        self.prior = self.root / ".pack-pending-unrelated"
        self.prior.write_bytes(b"owned by another invocation\n")

    def assert_prior(self):
        self.assertEqual(self.prior.read_bytes(), b"owned by another invocation\n")

    def test_complete_bytes_and_repeated_destinations(self):
        for name in ("first.json", "second.json"):
            output.publish_file(self.root / name, self.payload)
            self.assertEqual((self.root / name).read_bytes(), self.payload)
        self.assertEqual({p.name for p in self.root.iterdir()}, {self.prior.name, "first.json", "second.json"})
        self.assert_prior()

    def test_short_writes_complete_the_same_payload(self):
        original = os.write
        with patch.object(output.os, "write", side_effect=lambda fd, data: original(fd, data[:3])):
            output.publish_file(self.target, self.payload)
        self.assertEqual(self.target.read_bytes(), self.payload)

    def test_prepublication_failures_clean_owned_state_and_allow_retry(self):
        for phase in ("open", "write", "fsync", "link"):
            with self.subTest(phase=phase):
                original_open = os.open
                def open_stage(path, *args, **kwargs):
                    if str(path).startswith(".pack-pending-"):
                        raise OSError(errno.EIO, "private fixture location")
                    return original_open(path, *args, **kwargs)
                fault = patch.object(output.os, "open", side_effect=open_stage) if phase == "open" else patch.object(output.os, phase, side_effect=OSError(errno.EIO, "private fixture location"))
                with fault, self.assertRaises(output.OutputPublicationError) as caught:
                    output.publish_file(self.target, self.payload)
                self.assertEqual(caught.exception.code, "output_io")
                self.assertNotIn("private fixture", str(caught.exception))
                self.assertEqual({p.name for p in self.root.iterdir()}, {self.prior.name})
                output.publish_file(self.target, self.payload)
                self.assertEqual(self.target.read_bytes(), self.payload)
                self.target.unlink()
        self.assert_prior()

    def test_partial_write_then_failure_leaves_final_path_available(self):
        original = os.write
        count = 0
        def partial(fd, data):
            nonlocal count
            count += 1
            if count == 1:
                return original(fd, data[:4])
            raise OSError(errno.ENOSPC, "fixture")
        with patch.object(output.os, "write", side_effect=partial), self.assertRaises(output.OutputPublicationError):
            output.publish_file(self.target, self.payload)
        self.assertEqual({p.name for p in self.root.iterdir()}, {self.prior.name})
        output.publish_file(self.target, self.payload)
        self.assertEqual(self.target.read_bytes(), self.payload)

    def test_file_symlink_and_directory_collisions_preserve_targets(self):
        for kind in ("file", "symlink", "directory"):
            with self.subTest(kind=kind):
                if kind == "file": self.target.write_bytes(b"prior final\n")
                elif kind == "symlink": self.target.symlink_to(self.prior)
                else: self.target.mkdir()
                with self.assertRaises(output.OutputPublicationError) as caught:
                    output.publish_file(self.target, self.payload)
                self.assertEqual(caught.exception.code, "output_collision")
                if kind == "file": self.assertEqual(self.target.read_bytes(), b"prior final\n")
                elif kind == "symlink": self.assertTrue(self.target.is_symlink())
                else: self.assertTrue(self.target.is_dir())
                self.assert_prior()
                self.target.rmdir() if kind == "directory" else self.target.unlink()

    def test_staging_collision_preserves_foreign_file(self):
        class Fixed:
            hex = "unrelated"
        with patch.object(output, "uuid4", return_value=Fixed()), self.assertRaises(output.OutputPublicationError) as caught:
            output.publish_file(self.target, self.payload)
        self.assertEqual(caught.exception.code, "output_collision")
        self.assert_prior()

    def test_concurrent_publishers_expose_one_whole_payload(self):
        alternatives = (b"first\n", b"second\n")
        def publish(value):
            try:
                output.publish_file(self.target, value)
                return "completed"
            except output.OutputPublicationError as error:
                return error.code
        with ThreadPoolExecutor(max_workers=2) as pool:
            states = list(pool.map(publish, alternatives))
        self.assertCountEqual(states, ["completed", "output_collision"])
        self.assertIn(self.target.read_bytes(), alternatives)
        self.assertEqual({p.name for p in self.root.iterdir()}, {self.prior.name, self.target.name})

    def test_directory_sync_failure_retains_complete_final(self):
        original = os.fsync
        count = 0
        def fail_directory(fd):
            nonlocal count
            count += 1
            if count == 2: raise OSError(errno.EIO, "directory sync fixture")
            original(fd)
        with patch.object(output.os, "fsync", side_effect=fail_directory), self.assertRaises(output.OutputPublicationError) as caught:
            output.publish_file(self.target, self.payload)
        self.assertEqual(caught.exception.code, "output_uncertain")
        self.assertEqual(self.target.read_bytes(), self.payload)
        self.assertEqual({p.name for p in self.root.iterdir()}, {self.prior.name, self.target.name})

    def test_unsupported_link_preserves_final_absence(self):
        with patch.object(output.os, "link", side_effect=OSError(errno.ENOTSUP, "fixture")), self.assertRaises(output.OutputPublicationError) as caught:
            output.publish_file(self.target, self.payload)
        self.assertEqual(caught.exception.code, "output_platform")
        self.assertFalse(self.target.exists())

    def test_directory_close_failure_reports_the_visible_complete_file(self):
        original = os.close
        def close_then_fail(fd):
            directory = stat.S_ISDIR(os.fstat(fd).st_mode)
            original(fd)
            if directory:
                raise OSError(errno.EIO, "private close fixture")
        with patch.object(output.os, "close", side_effect=close_then_fail), self.assertRaises(output.OutputPublicationError) as caught:
            output.publish_file(self.target, self.payload)
        self.assertEqual(caught.exception.code, "output_uncertain")
        self.assertEqual(self.target.read_bytes(), self.payload)
        self.assertEqual({p.name for p in self.root.iterdir()}, {self.prior.name, self.target.name})

    def test_retained_program_profile_skips_only_the_administrative_cli_cases(self):
        import runpy
        def available(name):
            return object() if name == "lims_eln_contracts" else None
        with patch("importlib.util.find_spec", side_effect=available):
            module = runpy.run_path(__file__, run_name="profile_fixture")
        cls = module["AtomicOutputTests"]
        for name in ("test_real_pack_cli_roundtrip_and_collision", "test_cli_termination_after_link_explains_recovery"):
            self.assertTrue(getattr(cls, name).__unittest_skip__)
        self.assertFalse(getattr(cls.test_complete_bytes_and_repeated_destinations, "__unittest_skip__", False))

    def test_destination_and_payload_boundaries(self):
        for payload in (b"", "text", b"x" * (output.MAX_OUTPUT_BYTES + 1)):
            with self.subTest(payload=type(payload).__name__), self.assertRaises(output.OutputPublicationError) as caught:
                output.publish_file(self.target, payload)
            self.assertEqual(caught.exception.code, "output_payload")
        linked = self.root / "linked"
        linked.symlink_to(self.root, target_is_directory=True)
        with self.assertRaises(output.OutputPublicationError) as caught:
            output.publish_file(linked / "pack.json", self.payload)
        self.assertEqual(caught.exception.code, "output_destination")

    def test_interrupt_at_acquisition_write_and_publication(self):
        code = '''import os, pathlib, signal, sys
from lims_eln_sim import atomic_output as output
target, phase = pathlib.Path(sys.argv[1]), sys.argv[2]
def interrupted(number, _frame): raise SystemExit(128 + number)
signal.signal(signal.SIGTERM, interrupted)
original_open, original_write, original_link = os.open, os.write, os.link
def opened(path, *args, **kwargs):
    fd = original_open(path, *args, **kwargs)
    if phase == "acquire" and str(path).startswith(".pack-pending-"): os.kill(os.getpid(), signal.SIGTERM)
    return fd
def written(fd, data):
    result = original_write(fd, data[:3])
    if phase == "write": os.kill(os.getpid(), signal.SIGTERM)
    return result
def linked(*args, **kwargs):
    result = original_link(*args, **kwargs)
    if phase == "publish": os.kill(os.getpid(), signal.SIGTERM)
    return result
os.open, os.write, os.link = opened, written, linked
output.publish_file(target, b"complete fixture\\n")
'''
        for phase in ("acquire", "write", "publish"):
            with self.subTest(phase=phase):
                process = subprocess.run([sys.executable, "-B", "-c", code, str(self.target), phase],
                                         capture_output=True, text=True, timeout=10)
                self.assertEqual(process.returncode, 128 + signal.SIGTERM, process.stderr)
                if phase == "publish":
                    self.assertEqual(self.target.read_bytes(), b"complete fixture\n")
                    self.target.unlink()
                self.assertEqual({p.name for p in self.root.iterdir()}, {self.prior.name})
                output.publish_file(self.target, self.payload)
                self.target.unlink()
                self.assert_prior()

    @unittest.skipUnless(HAS_ADMINISTRATIVE_STUDY, "administrative-study extra supplies Program admission")
    def test_real_pack_cli_roundtrip_and_collision(self):
        from lims_eln_contracts.canonical import canonical_json_bytes
        from lims_eln_sim.administrative_pack import admit_pack, build_pack
        command = [sys.executable, "-B", "-m", "lims_eln_sim.administrative_pack", "--output", str(self.target), "--repeats", "1"]
        first = subprocess.run(command, capture_output=True, text=True, timeout=20)
        self.assertEqual(first.returncode, 0, first.stderr)
        expected = canonical_json_bytes(build_pack(repeats=1)) + b"\n"
        self.assertEqual(self.target.read_bytes(), expected)
        self.assertEqual(admit_pack(expected), build_pack(repeats=1))
        repeated = subprocess.run(command, capture_output=True, text=True, timeout=20)
        self.assertEqual(repeated.returncode, 2)
        self.assertIn("output_collision", repeated.stderr)
        self.assertNotIn(str(self.root), repeated.stderr)
        self.assertEqual(self.target.read_bytes(), expected)

    @unittest.skipUnless(HAS_ADMINISTRATIVE_STUDY, "administrative-study extra supplies Program admission")
    def test_cli_termination_after_link_explains_recovery(self):
        from lims_eln_sim.administrative_pack import admit_pack
        code = '''import os, signal, sys
from lims_eln_sim import atomic_output as output
from lims_eln_sim.administrative_pack import main
original = os.link
def linked(*args, **kwargs):
    result = original(*args, **kwargs)
    os.kill(os.getpid(), signal.SIGTERM)
    return result
output.os.link = linked
sys.argv = ["pack", "--output", sys.argv[1], "--repeats", "1"]
main()
'''
        process = subprocess.run([sys.executable, "-B", "-c", code, str(self.target)],
                                 capture_output=True, text=True, timeout=20)
        self.assertEqual(process.returncode, 128 + signal.SIGTERM)
        self.assertIn("output_uncertain", process.stderr)
        self.assertNotIn(str(self.root), process.stderr)
        self.assertEqual(len(admit_pack(self.target.read_bytes()).study.runs), 72)
        self.assertEqual({p.name for p in self.root.iterdir()}, {self.prior.name, self.target.name})


if __name__ == "__main__":
    unittest.main()
