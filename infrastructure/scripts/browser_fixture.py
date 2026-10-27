"""Run the portfolio browser workflow against a disposable database, never live accounts."""

import json
import os
import secrets
import signal
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from urllib.error import URLError
from urllib.request import urlopen
from uuid import uuid4

from app.core.security import password_hash
from app.modules.identity.models import User
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

ROOT = Path(__file__).resolve().parents[2]


def run_browser(environment: dict[str, str]) -> None:
    env = dict(environment)
    env["CISRICE_E2E_EMAIL"] = f"browser-{uuid4().hex}@example.test"
    env["CISRICE_E2E_PASSWORD"] = secrets.token_urlsafe(24)
    env["CISRICE_E2E_URL"] = "http://127.0.0.1:14173"
    env["CISRICE_API_URL"] = "http://127.0.0.1:18000"
    env["ALLOWED_ORIGINS"] = json.dumps(["http://127.0.0.1:14173"])
    env["RATE_NAMESPACE"] = "cisrice-e2e-" + uuid4().hex
    engine = create_engine(env["DATABASE_URL"])
    with Session(engine) as database, database.begin():
        database.add(
            User(
                email=env["CISRICE_E2E_EMAIL"],
                password_hash=password_hash(env["CISRICE_E2E_PASSWORD"]),
            )
        )
    engine.dispose()
    processes: list[subprocess.Popen[str]] = []
    with tempfile.TemporaryFile(mode="w+t") as log:
        try:
            for command, cwd in [
                (
                    [
                        sys.executable,
                        "-m",
                        "uvicorn",
                        "app.main:app",
                        "--host",
                        "127.0.0.1",
                        "--port",
                        "18000",
                    ],
                    ROOT / "backend",
                ),
                (
                    ["npm", "run", "preview", "--", "--port", "14173", "--strictPort"],
                    ROOT / "frontend",
                ),
            ]:
                processes.append(
                    subprocess.Popen(
                        command,
                        cwd=cwd,
                        env=env,
                        stdin=subprocess.DEVNULL,
                        stdout=log,
                        stderr=subprocess.STDOUT,
                        text=True,
                        start_new_session=True,
                    )
                )
            for url in ["http://127.0.0.1:18000/api/health/ready", env["CISRICE_E2E_URL"]]:
                deadline = time.monotonic() + 30
                while True:
                    try:
                        with urlopen(url, timeout=2) as response:
                            if response.status == 200:
                                break
                    except (URLError, TimeoutError):
                        pass
                    if time.monotonic() >= deadline or any(p.poll() is not None for p in processes):
                        log.seek(0)
                        print(log.read())
                        raise RuntimeError("Isolated browser test servers did not become ready")
                    time.sleep(0.2)
            subprocess.run(
                ["npx", "playwright", "test"],
                cwd=ROOT / "frontend",
                env=env,
                stdin=subprocess.DEVNULL,
                check=True,
                timeout=180,
            )
            print("PASS isolated browser portfolio workflow", flush=True)
        finally:
            for process in reversed(processes):
                try:
                    os.killpg(process.pid, signal.SIGTERM)
                except ProcessLookupError:
                    pass
                try:
                    process.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    os.killpg(process.pid, signal.SIGKILL)
                    process.wait(timeout=5)
