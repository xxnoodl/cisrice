"""Immutable content-addressed storage. Only validated local files enter canonical storage."""

import hashlib
import json
import os
import re
import shutil
import subprocess
import time
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path


class MediaError(ValueError):
    def __init__(self, code: str, retry_after: int = 0) -> None:
        super().__init__(code)
        self.retry_after = min(86400, max(0, retry_after))


@dataclass(frozen=True)
class MediaInfo:
    extension: str
    mime: str
    duration: float
    width: int
    height: int
    video_codec: str
    audio_codec: str | None


def digest(path: Path, heartbeat: Callable[[int], None] | None = None) -> str:
    value = hashlib.sha256()
    last = time.monotonic()
    with path.open("rb") as handle:
        while chunk := handle.read(1024 * 1024):
            value.update(chunk)
            if heartbeat and time.monotonic() - last > 1:
                heartbeat(95)
                last = time.monotonic()
    return value.hexdigest()


class MediaStorage:
    def __init__(self, root: str, quota: int, minimum_free: int) -> None:
        self.root = Path(root).resolve()
        self.quota, self.minimum_free = quota, minimum_free
        self.root.mkdir(parents=True, exist_ok=True)

    def path(self, relative: str) -> Path:
        value = (self.root / relative).resolve()
        if not value.is_relative_to(self.root) or value == self.root:
            raise MediaError("unsafe_storage_path")
        return value

    def reserve(self, size: int) -> None:
        used = sum(
            p.stat().st_size
            for folder in ["objects", "staging", "quarantine"]
            for p in self.path(folder).rglob("*")
            if p.is_file()
        )
        if size < 0 or used + size > self.quota:
            raise MediaError("storage_quota_exceeded")
        if shutil.disk_usage(self.root).free - size < self.minimum_free:
            raise MediaError("insufficient_disk_space")

    def staging(self, job: str, token: str) -> Path:
        if not re.fullmatch(r"[a-f0-9-]{32,36}", job) or not re.fullmatch(
            r"[a-f0-9-]{32,36}", token
        ):
            raise MediaError("invalid_staging_identifier")
        result = self.path(f"staging/{job}/{token}")
        result.mkdir(parents=True, exist_ok=False)
        return result

    def canonical(self, sha256: str, extension: str) -> Path:
        if not re.fullmatch(r"[a-f0-9]{64}", sha256) or extension not in {"mp4", "webm", "mkv"}:
            raise MediaError("invalid_object_identifier")
        return self.path(f"objects/sha256/{sha256[:2]}/{sha256[2:4]}/{sha256}.{extension}")

    def commit(
        self, staged: Path, extension: str, heartbeat: Callable[[int], None] | None = None
    ) -> tuple[str, Path]:
        if not staged.resolve().is_relative_to(self.path("staging")) or staged.is_symlink():
            raise MediaError("unsafe_staging_path")
        sha256 = digest(staged, heartbeat)
        target = self.canonical(sha256, extension)
        target.parent.mkdir(parents=True, exist_ok=True)
        try:
            # Atomic no-overwrite installation; staging and objects use the same volume.
            os.link(staged, target)
            target.chmod(0o444)
        except FileExistsError:
            if target.is_symlink() or not target.is_file() or digest(target, heartbeat) != sha256:
                raise MediaError("canonical_object_corrupt") from None
        return sha256, target

    def quarantine(self, staged: Path, job: str) -> None:
        if not re.fullmatch(r"[a-f0-9-]{32,36}", job) or not staged.resolve().is_relative_to(
            self.path("staging")
        ):
            raise MediaError("unsafe_quarantine_path")
        target = self.path("quarantine/" + job)
        target.parent.mkdir(parents=True, exist_ok=True)
        if staged.is_file() and not target.exists():
            staged.rename(target)


def probe(path: Path, max_seconds: int = 7200) -> MediaInfo:
    try:
        with path.open("rb") as stream:
            magic = stream.read(16)
        if not (magic.startswith(b"\x1aE\xdf\xa3") or magic[4:8] == b"ftyp"):
            raise MediaError("unsupported_media_container")
        result = subprocess.run(
            [
                "ffprobe",
                "-v",
                "error",
                "-protocol_whitelist",
                "file",
                "-format_whitelist",
                "mov,matroska,webm",
                "-show_entries",
                "format=format_name,duration:stream=codec_type,codec_name,width,height",
                "-of",
                "json",
                "-i",
                str(path),
            ],
            capture_output=True,
            timeout=20,
            check=True,
        )
        if len(result.stdout) > 1024 * 1024:
            raise MediaError("probe_output_too_large")
        data = json.loads(result.stdout)
        video = next(s for s in data["streams"] if s["codec_type"] == "video")
        audio = next((s for s in data["streams"] if s["codec_type"] == "audio"), None)
        duration = float(data["format"]["duration"])
        width, height = int(video["width"]), int(video["height"])
        if not 0 < duration <= max_seconds or not 0 < width <= 7680 or not 0 < height <= 7680:
            raise MediaError("invalid_media_dimensions_or_duration")
        formats = data["format"]["format_name"].split(",")
        extension = (
            "mp4"
            if "mov" in formats
            else "webm"
            if video["codec_name"] in {"vp8", "vp9", "av1"}
            else "mkv"
        )
        return MediaInfo(
            extension,
            "video/mp4"
            if extension == "mp4"
            else "video/webm"
            if extension == "webm"
            else "video/x-matroska",
            duration,
            width,
            height,
            str(video["codec_name"]),
            str(audio["codec_name"]) if audio else None,
        )
    except FileNotFoundError:
        raise MediaError("ffprobe_not_installed") from None
    except (subprocess.SubprocessError, OSError, ValueError, KeyError, StopIteration, TypeError):
        raise MediaError("invalid_media") from None


def validate_decode(path: Path, heartbeat: Callable[[int], None]) -> None:
    try:
        with subprocess.Popen(
            [
                "ffmpeg",
                "-nostdin",
                "-v",
                "error",
                "-threads",
                "2",
                "-xerror",
                "-err_detect",
                "explode",
                "-protocol_whitelist",
                "file",
                "-format_whitelist",
                "mov,matroska,webm",
                "-i",
                str(path),
                "-map",
                "0:v:0",
                "-map",
                "0:a?",
                "-f",
                "null",
                "-",
            ],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        ) as process:
            try:
                deadline = time.monotonic() + 120
                while process.poll() is None:
                    heartbeat(90)
                    if time.monotonic() > deadline:
                        raise MediaError("validation_timeout")
                    time.sleep(0.5)
                if process.returncode:
                    raise MediaError("media_decode_failed")
            finally:
                if process.poll() is None:
                    process.kill()
                    process.wait(timeout=5)
    except FileNotFoundError:
        raise MediaError("ffmpeg_not_installed") from None
