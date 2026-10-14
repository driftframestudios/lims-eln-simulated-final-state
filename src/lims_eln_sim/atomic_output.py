"""Publish a bounded file exclusively through an owned POSIX directory.

The caller admits the complete payload before entry. Publication costs O(B)
time for B bytes and O(1) additional space through a memoryview. A hard link
provides atomic visibility and exclusive creation; file and directory fsync
request durability from the selected filesystem.
"""
from __future__ import annotations

from contextlib import contextmanager
import errno
import os
from pathlib import Path
import signal
import stat
from uuid import uuid4


MAX_OUTPUT_BYTES = 2_097_152
_RECOVERY = {
    "output_payload": "Supply the complete admitted bounded byte payload.",
    "output_platform": "Select a POSIX filesystem with directory handles, hard links and fsync.",
    "output_destination": "Select a concrete caller-owned directory with exclusive write ownership.",
    "output_collision": "Preserve the existing destination and choose a fresh output name.",
    "output_io": "Restore destination access and retry with the admitted payload.",
    "output_uncertain": "Inspect and admit the existing complete destination before choosing a fresh retry name.",
}


class OutputPublicationError(ValueError):
    """Fixed recovery messages keep protected locators with the caller."""

    def __init__(self, code: str):
        self.code = code
        self.recovery = _RECOVERY[code]
        super().__init__(f"{code}: {self.recovery}")


class OutputPublicationInterrupted(SystemExit):
    """Retain termination status while naming a visible complete destination."""

    recovery = "output_uncertain: " + _RECOVERY["output_uncertain"]


@contextmanager
def _defer_termination():
    """Record resource ownership before a handled signal can unwind the call."""
    previous = signal.pthread_sigmask(signal.SIG_BLOCK, {signal.SIGINT, signal.SIGTERM})
    try:
        yield
    finally:
        signal.pthread_sigmask(signal.SIG_SETMASK, previous)


def publish_file(destination: Path, payload: bytes) -> None:
    """Expose complete bytes once; existing targets retain their exact content.

    The parent directory must already exist. Its ancestors and concurrent
    same-account writers belong to the caller's trusted filesystem boundary.
    SIGKILL or power loss may retain an owned .pack-pending-* file; final names
    still expose complete bytes. An error after linking reports uncertainty,
    retaining the complete destination for caller inspection.
    """
    if type(payload) is not bytes or not 0 < len(payload) <= MAX_OUTPUT_BYTES:
        raise OutputPublicationError("output_payload")
    if (os.name != "posix" or not hasattr(signal, "pthread_sigmask")
            or not getattr(os, "O_NOFOLLOW", 0) or not getattr(os, "O_DIRECTORY", 0)):
        raise OutputPublicationError("output_platform")
    destination = Path(destination)
    if destination.name in {"", ".", ".."}:
        raise OutputPublicationError("output_destination")
    root_fd = None
    file_fd = None
    staging = ".pack-pending-" + uuid4().hex
    owned = False
    published = False
    try:
        try:
            try:
                with _defer_termination():
                    root_fd = os.open(destination.parent, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
            except OSError:
                raise OutputPublicationError("output_destination") from None
            info = os.fstat(root_fd)
            if info.st_uid != os.getuid() or info.st_mode & 0o022:
                raise OutputPublicationError("output_destination")
            try:
                with _defer_termination():
                    file_fd = os.open(staging, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
                                      0o600, dir_fd=root_fd)
                    owned = True
                view = memoryview(payload)
                offset = 0
                while offset < len(view):
                    written = os.write(file_fd, view[offset:])
                    if written <= 0:
                        raise OSError(errno.EIO, "complete write required")
                    offset += written
                os.fsync(file_fd)
                with _defer_termination():
                    os.link(staging, destination.name, src_dir_fd=root_fd,
                            dst_dir_fd=root_fd, follow_symlinks=False)
                    published = True
                os.fsync(root_fd)
            finally:
                with _defer_termination():
                    try:
                        if owned:
                            os.unlink(staging, dir_fd=root_fd)
                    finally:
                        if file_fd is not None:
                            os.close(file_fd)
        finally:
            if root_fd is not None:
                os.close(root_fd)
    except (SystemExit, KeyboardInterrupt) as error:
        if published:
            status = error.code if isinstance(error, SystemExit) else 128 + signal.SIGINT
            raise OutputPublicationInterrupted(status) from None
        raise
    except OSError as error:
        if published:
            code = "output_uncertain"
        elif isinstance(error, FileExistsError):
            code = "output_collision"
        elif error.errno in {errno.ENOSYS, errno.ENOTSUP, errno.EXDEV}:
            code = "output_platform"
        else:
            code = "output_io"
        raise OutputPublicationError(code) from None
