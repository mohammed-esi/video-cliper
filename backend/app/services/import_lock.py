import threading
from contextlib import contextmanager
from typing import Iterator

from app.core.errors import ImportInProgressError

_lock = threading.Lock()


@contextmanager
def media_import_lock() -> Iterator[None]:
    acquired = _lock.acquire(blocking=False)
    if not acquired:
        raise ImportInProgressError()
    try:
        yield
    finally:
        _lock.release()
