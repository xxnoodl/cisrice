import shutil
import subprocess
from pathlib import Path

import pytest

from app.modules.acquisition.storage import MediaError, MediaStorage, digest, probe, validate_decode


@pytest.fixture
def clip(tmp_path: Path) -> Path:
    if not shutil.which("ffmpeg") or not shutil.which("ffprobe"):
        pytest.skip("FFmpeg/ffprobe required for real media validation")
    path = tmp_path / "fixture.mp4"
    subprocess.run(
        [
            "ffmpeg",
            "-nostdin",
            "-v",
            "error",
            "-f",
            "lavfi",
            "-i",
            "color=c=blue:s=160x90:d=1",
            "-f",
            "lavfi",
            "-i",
            "sine=frequency=440:duration=1",
            "-c:v",
            "libx264",
            "-threads",
            "1",
            "-pix_fmt",
            "yuv420p",
            "-c:a",
            "aac",
            "-shortest",
            "-movflags",
            "+faststart",
            str(path),
        ],
        check=True,
        timeout=30,
        stdin=subprocess.DEVNULL,
    )
    return path


def test_real_media_validation_and_canonical_dedup(tmp_path: Path, clip: Path) -> None:
    from uuid import uuid4

    storage = MediaStorage(str(tmp_path / "storage"), 10 * 1024**2, 0)
    path = storage.staging(str(uuid4()), str(uuid4())) / "source.part"
    shutil.copyfile(clip, path)
    info = probe(path)
    assert info.width == 160 and info.height == 90 and info.audio_codec == "aac"
    validate_decode(path, lambda _: None)
    first, target = storage.commit(path, info.extension)
    assert digest(target) == first
    assert storage.commit(path, info.extension) == (first, target)
    assert len(list(storage.path("objects").rglob("*.mp4"))) == 1
    assert (
        target.relative_to(storage.root)
        .as_posix()
        .startswith("objects/sha256/" + first[:2] + "/" + first[2:4])
    )


def test_storage_paths_quotas_and_invalid_media(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    storage = MediaStorage(str(tmp_path / "storage"), 1024, 0)
    for relative in ["../outside", str(tmp_path / "outside")]:
        with pytest.raises(MediaError):
            storage.path(relative)
    with pytest.raises(MediaError):
        storage.canonical("../bad", "mp4")
    with pytest.raises(MediaError):
        storage.staging("../bad", "bad")
    with pytest.raises(MediaError, match="quota"):
        storage.reserve(1025)
    monkeypatch.setattr(shutil, "disk_usage", lambda _: type("Disk", (), {"free": 0})())
    with pytest.raises(MediaError, match="disk_space"):
        storage.reserve(1)
    invalid = tmp_path / "invalid.mp4"
    invalid.write_bytes(b"not media")
    with pytest.raises(MediaError):
        probe(invalid)


def test_corrupt_canonical_is_not_overwritten(tmp_path: Path, clip: Path) -> None:
    from uuid import uuid4

    storage = MediaStorage(str(tmp_path / "storage"), 10 * 1024**2, 0)
    stage = storage.staging(str(uuid4()), str(uuid4())) / "source.part"
    shutil.copyfile(clip, stage)
    target = storage.canonical(digest(stage), "mp4")
    target.parent.mkdir(parents=True)
    target.write_bytes(b"corrupt")
    with pytest.raises(MediaError, match="corrupt"):
        storage.commit(stage, "mp4")
    assert target.read_bytes() == b"corrupt"
