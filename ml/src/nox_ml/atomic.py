"""Writing a file that grows in place without leaving it half written.

The tables of a season are rewritten by every `nox-ml update`; a crash or a full disk in the middle of a
write would leave the file the analyses read truncated. `atomic_path` hands out a temporary path in the same
folder and moves it over the target only when the writer finished.
"""

import os
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path


@contextmanager
def atomic_path(path: Path) -> Iterator[Path]:
    """A temporary path next to `path` to write to; on a clean exit it replaces `path` (`os.replace`, atomic
    within a filesystem), on an exception it is deleted and `path` stays as it was."""
    tmp = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    try:
        yield tmp
        os.replace(tmp, path)
    except BaseException:
        tmp.unlink(missing_ok=True)
        raise


def write_text(path: Path, text: str) -> None:
    """`path.write_text(text)`, atomically."""
    with atomic_path(path) as tmp:
        tmp.write_text(text)
