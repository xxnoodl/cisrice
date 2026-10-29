"""Isolated worker fixture. Production entrypoints never import this module."""

import os
import shutil
from collections.abc import Callable
from pathlib import Path

from app.workers import acquisition_tasks
from app.workers.celery_app import celery_app as celery_app


def fixture_download(
    url: str,
    destination: Path,
    limit: int,
    heartbeat: Callable[[int], None],
    reserve: Callable[[int], None],
) -> None:
    if url != "https://example.org/owned.mp4":
        raise ValueError("Browser fixture only supports its explicitly generated test clip")
    path = Path(os.environ["CISRICE_MEDIA_FIXTURE"])
    if path.stat().st_size > limit:
        raise ValueError("Fixture exceeds configured limit")
    reserve(path.stat().st_size)
    shutil.copyfile(path, destination)
    heartbeat(75)


acquisition_tasks.download = fixture_download
