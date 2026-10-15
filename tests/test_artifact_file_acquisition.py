"""Finite file acquisition and owned cleanup at the artifact receiving boundary."""

import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import Mock, patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from lims_eln_sim import artifact_boundary as boundary


class ArtifactFileAcquisitionTests(unittest.TestCase):
    def setUp(self):
        self.root = Path(self.enterContext(tempfile.TemporaryDirectory()))
        self.path = self.root / "result.json"
        self.content = b'{"synthetic":true}\n'
        self.path.write_bytes(self.content)

    def test_regular_bytes_and_single_descriptor_release(self):
        close = os.close
        with patch.object(boundary.os, "close", wraps=close) as observed:
            self.assertEqual(self.content, boundary._read_regular_file(self.path, self.path.name))
        observed.assert_called_once()
        with self.assertRaises(OSError):
            os.fstat(observed.call_args.args[0])

    @unittest.skipUnless(hasattr(os, "mkfifo"), "requires a POSIX FIFO")
    def test_unopened_fifo_is_rejected_within_a_bounded_subprocess(self):
        self.path.unlink()
        os.mkfifo(self.path)
        code = '''import pathlib, sys
sys.path.insert(0, sys.argv[1])
from lims_eln_sim.artifact_boundary import ArtifactBoundaryError, artifact_inventory
try:
    artifact_inventory(pathlib.Path(sys.argv[2]))
except ArtifactBoundaryError as error:
    assert "requires a regular output file" in str(error), str(error)
else:
    raise AssertionError("FIFO was admitted")
'''
        result = subprocess.run(
            [sys.executable, "-B", "-c", code, str(ROOT / "src"), str(self.root)],
            capture_output=True, text=True, timeout=5,
        )
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertEqual("", result.stdout)

    def test_symlink_leaf_retains_its_target(self):
        link = self.root / "linked.json"
        link.symlink_to(self.path)
        with self.assertRaises(boundary.ArtifactBoundaryError):
            boundary._read_regular_file(link, link.name)
        self.assertEqual(self.content, self.path.read_bytes())

    def test_fdopen_failure_releases_the_owned_descriptor(self):
        failure = OSError("synthetic stream setup failure")
        close = os.close
        with patch.object(boundary.os, "fdopen", side_effect=failure), \
             patch.object(boundary.os, "close", wraps=close) as observed:
            with self.assertRaises(OSError) as caught:
                boundary._read_regular_file(self.path, self.path.name)
        self.assertIs(failure, caught.exception)
        observed.assert_called_once()
        with self.assertRaises(OSError):
            os.fstat(observed.call_args.args[0])

    def test_descriptor_cleanup_failure_preserves_setup_failure(self):
        failure = OSError("synthetic stream setup failure")
        cleanup = OSError("synthetic descriptor cleanup observation")
        close = os.close
        def close_then_report(descriptor):
            close(descriptor)
            raise cleanup
        with patch.object(boundary.os, "fdopen", side_effect=failure), \
             patch.object(boundary.os, "close", side_effect=close_then_report) as observed:
            with self.assertRaises(OSError) as caught:
                boundary._read_regular_file(self.path, self.path.name)
        self.assertIs(failure, caught.exception)
        self.assertIs(cleanup, caught.exception.cleanup_error)
        observed.assert_called_once()

    def test_read_failure_and_interruption_retain_both_cleanup_observations(self):
        for failure in (OSError("synthetic read failure"), KeyboardInterrupt(), SystemExit(143)):
            with self.subTest(kind=type(failure).__name__):
                stream_error, descriptor_error = OSError("stream cleanup"), OSError("descriptor cleanup")
                stream = Mock()
                stream.read.side_effect = failure
                stream.close.side_effect = stream_error
                close = os.close
                def close_then_report(descriptor):
                    close(descriptor)
                    raise descriptor_error
                with patch.object(boundary.os, "fdopen", return_value=stream) as opened, \
                     patch.object(boundary.os, "close", side_effect=close_then_report) as closed:
                    with self.assertRaises(type(failure)) as caught:
                        boundary._read_regular_file(self.path, self.path.name)
                self.assertIs(failure, caught.exception)
                self.assertEqual((stream_error, descriptor_error), failure.cleanup_error.exceptions)
                self.assertIs(False, opened.call_args.kwargs["closefd"])
                stream.close.assert_called_once()
                closed.assert_called_once()

    def test_cleanup_failure_after_success_remains_visible(self):
        stream = Mock()
        stream.read.return_value = self.content
        failure = OSError("synthetic stream cleanup observation")
        stream.close.side_effect = failure
        close = os.close
        with patch.object(boundary.os, "fdopen", return_value=stream), \
             patch.object(boundary.os, "close", wraps=close) as closed:
            with self.assertRaises(OSError) as caught:
                boundary._read_regular_file(self.path, self.path.name)
        self.assertIs(failure, caught.exception)
        closed.assert_called_once()

    def test_nonblocking_support_is_an_explicit_platform_boundary(self):
        with patch.object(boundary.os, "O_NONBLOCK", None), \
             patch.object(boundary.os, "open") as opened:
            with self.assertRaisesRegex(boundary.ArtifactBoundaryError, "nonblocking"):
                boundary._read_regular_file(self.path, self.path.name)
        opened.assert_not_called()


if __name__ == "__main__":
    unittest.main()
