import threading
import time
import uuid
from pathlib import Path
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from app.core.config import get_settings
from app.main import create_app
from app.services import ffmpeg_runner
from app.services.processing_worker import shutdown, start


def test_shutdown_terminates_active_ffmpeg() -> None:
    started = threading.Event()
    release = threading.Event()

    def fake_popen(*_args, **_kwargs):
        class _Proc:
            pid = 12345

            def poll(self):
                return None if not release.is_set() else 0

            def communicate(self, timeout=None):
                started.set()
                release.wait(timeout=5.0)
                return "", ""

            def terminate(self):
                release.set()

            def kill(self):
                release.set()

            def wait(self, timeout=None):
                release.wait(timeout=timeout)
                return 0

            returncode = 0

        return _Proc()

    with patch("app.services.ffmpeg_runner.subprocess.Popen", side_effect=fake_popen):
        thread = threading.Thread(
            target=lambda: ffmpeg_runner.run_ffmpeg(["ffmpeg", "-version"], timeout_seconds=5.0),
        )
        thread.start()
        assert started.wait(timeout=2.0)
        ffmpeg_runner.terminate_active_process()
        thread.join(timeout=2.0)
        assert not thread.is_alive()
