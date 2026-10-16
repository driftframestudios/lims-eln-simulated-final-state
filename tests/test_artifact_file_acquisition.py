"""Finite file acquisition and owned cleanup at the artifact receiving boundary."""

import io
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
        # Public fault probes enter file acquisition after complete membership.
        for name in boundary.SIMULATION_ARTIFACTS:
            (self.root / name).write_bytes(self.content)

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

    def test_stream_construction_failure_releases_the_owned_descriptor(self):
        for constructor in ("FileIO", "BufferedReader"):
            with self.subTest(constructor=constructor):
                failure = OSError("synthetic stream setup failure")
                close = os.close
                with patch.object(boundary.io, constructor, side_effect=failure), \
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
        with patch.object(boundary.io, "FileIO", side_effect=failure), \
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
                with patch.object(boundary.io, "BufferedReader", return_value=stream), \
                     patch.object(boundary.os, "close", side_effect=close_then_report) as closed:
                    with self.assertRaises(type(failure)) as caught:
                        boundary._read_regular_file(self.path, self.path.name)
                self.assertIs(failure, caught.exception)
                self.assertEqual((stream_error, descriptor_error), failure.cleanup_error.exceptions)
                stream.close.assert_called_once()
                closed.assert_called_once()

    def test_cleanup_failure_after_success_remains_visible(self):
        stream = Mock()
        stream.read.return_value = self.content
        failure = OSError("synthetic stream cleanup observation")
        stream.close.side_effect = failure
        close = os.close
        with patch.object(boundary.io, "BufferedReader", return_value=stream), \
             patch.object(boundary.os, "close", wraps=close) as closed:
            with self.assertRaises(OSError) as caught:
                boundary._read_regular_file(self.path, self.path.name)
        self.assertIs(failure, caught.exception)
        closed.assert_called_once()

    def test_public_read_cleanup_keeps_later_descriptor_owner_untouched(self):
        for primary_kind in (None, OSError, KeyboardInterrupt, SystemExit):
            for cleanup_kind in (OSError, KeyboardInterrupt, SystemExit):
                with self.subTest(primary=primary_kind, cleanup=cleanup_kind):
                    primary = primary_kind() if primary_kind else None
                    cleanup = cleanup_kind()
                    retained = []

                    class InterruptedReader(io.BufferedReader):
                        def read(reader, *args):
                            content = super().read(*args)
                            self.assertEqual(self.content, content)
                            if primary is not None:
                                raise primary
                            return content

                        def close(reader):
                            raise cleanup

                    def reader_for(raw):
                        reader = InterruptedReader(raw)
                        retained.append((reader, raw.fileno()))
                        return reader

                    close = os.close
                    with patch.object(boundary.io, "BufferedReader", side_effect=reader_for), \
                         patch.object(boundary.os, "close", wraps=close) as closed:
                        with self.assertRaises(BaseException) as caught:
                            boundary.artifact_inventory(self.root)
                    self.assertIs(primary if primary is not None else cleanup, caught.exception)
                    if primary is not None:
                        self.assertIs(cleanup, primary.cleanup_error)
                    reader, old_descriptor = retained[0]
                    self.assertTrue(reader.raw.closed)
                    closed.assert_called_once_with(old_descriptor)
                    later_path = self.root / "later.json"
                    later_path.write_bytes(b"later-owner-bytes")
                    later_descriptor = os.open(later_path, os.O_RDONLY)
                    try:
                        self.assertEqual(old_descriptor, later_descriptor)
                        with self.assertRaises(ValueError):
                            reader.read(1)
                        self.assertEqual(0, os.lseek(later_descriptor, 0, os.SEEK_CUR))
                        self.assertEqual(b"later-owner-bytes", os.read(later_descriptor, 32))
                    finally:
                        os.close(later_descriptor)
                        later_path.unlink()
                    self.assertEqual(self.content, self.path.read_bytes())

    def test_live_raw_reader_retains_ordered_recovery_through_public_error(self):
        for primary_kind in (None, OSError, KeyboardInterrupt, SystemExit):
            with self.subTest(primary=primary_kind):
                primary = primary_kind() if primary_kind else None
                stream_error, raw_error = OSError("buffer close"), OSError("raw close")
                retained = []

                class HeldRaw(io.FileIO):
                    held = True

                    def close(raw):
                        if raw.held:
                            raise raw_error
                        return super().close()

                class HeldReader(io.BufferedReader):
                    def read(reader, *args):
                        content = super().read(*args)
                        if primary is not None:
                            raise primary
                        return content

                    def close(reader):
                        raise stream_error

                def raw_for(descriptor, *args, **kwargs):
                    raw = HeldRaw(descriptor, *args, **kwargs)
                    retained.append((raw, descriptor))
                    return raw

                with patch.object(boundary.io, "FileIO", side_effect=raw_for), \
                     patch.object(boundary.io, "BufferedReader", HeldReader), \
                     patch.object(boundary.os, "close") as closed:
                    with self.assertRaises(BaseException) as caught:
                        boundary.artifact_inventory(self.root)
                raw, descriptor = retained[0]
                try:
                    if primary is not None:
                        self.assertIs(primary, caught.exception)
                        errors = primary.cleanup_error
                    else:
                        errors = caught.exception
                    self.assertEqual((stream_error, raw_error), errors.exceptions)
                    self.assertIs(raw, caught.exception.retained_stream)
                    self.assertEqual(descriptor, caught.exception.retained_descriptor)
                    self.assertFalse(raw.closed)
                    os.fstat(descriptor)
                    closed.assert_not_called()
                finally:
                    raw.held = False
                    raw.close()
                    self.assertTrue(raw.closed)
                    os.close(descriptor)
                self.assertEqual(self.content, self.path.read_bytes())

    def test_raw_close_observation_after_invalidation_releases_descriptor(self):
        stream_error = KeyboardInterrupt()
        raw_error = OSError("closed raw stream")
        retained = []

        class ClosedRaw(io.FileIO):
            def close(raw):
                super().close()
                raise raw_error

        class InterruptedReader(io.BufferedReader):
            def close(reader):
                raise stream_error

        def raw_for(descriptor, *args, **kwargs):
            raw = ClosedRaw(descriptor, *args, **kwargs)
            retained.append((raw, descriptor))
            return raw

        close = os.close
        with patch.object(boundary.io, "FileIO", side_effect=raw_for), \
             patch.object(boundary.io, "BufferedReader", InterruptedReader), \
             patch.object(boundary.os, "close", wraps=close) as closed:
            with self.assertRaises(BaseExceptionGroup) as caught:
                boundary.artifact_inventory(self.root)
        raw, descriptor = retained[0]
        self.assertTrue(raw.closed)
        self.assertEqual((stream_error, raw_error), caught.exception.exceptions)
        self.assertFalse(hasattr(caught.exception, "retained_descriptor"))
        closed.assert_called_once_with(descriptor)
        with self.assertRaises(OSError):
            os.fstat(descriptor)

    def test_nonblocking_support_is_an_explicit_platform_boundary(self):
        with patch.object(boundary.os, "O_NONBLOCK", None), \
             patch.object(boundary.os, "open") as opened:
            with self.assertRaisesRegex(boundary.ArtifactBoundaryError, "nonblocking"):
                boundary._read_regular_file(self.path, self.path.name)
        opened.assert_not_called()


if __name__ == "__main__":
    unittest.main()
