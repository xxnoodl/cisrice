"""Verify the running Linux Compose stack using a newly created disposable database.

Run from the repository root with .venv/bin/python infrastructure/scripts/verify_linux.py.
Requires backend[dev], Docker access and an already running Compose stack. It connects
through Linux bridge addresses; Docker Desktop is not supported by this verifier.
The application database and volumes are never downgraded or removed.
"""

import json
import os
import subprocess
import sys
from pathlib import Path
from urllib.request import urlopen
from uuid import uuid4

import psycopg
from dotenv import dotenv_values
from psycopg import sql
from sqlalchemy.engine import make_url

ROOT = Path(__file__).resolve().parents[2]


def docker(*args: str) -> str:
    return subprocess.check_output(
        ["docker", "compose", *args], cwd=ROOT, text=True, stdin=subprocess.DEVNULL
    ).strip()


def address(service: str) -> str:
    container = docker("ps", "-q", service)
    networks = json.loads(
        subprocess.check_output(
            [
                "docker",
                "inspect",
                "--format",
                "{{json .NetworkSettings.Networks}}",
                container,
            ],
            text=True,
            stdin=subprocess.DEVNULL,
        )
    )
    addresses = [network["IPAddress"] for network in networks.values() if network["IPAddress"]]
    if len(addresses) != 1:
        raise RuntimeError("Verifier requires exactly one IPv4 bridge per service")
    return str(addresses[0])


def main() -> None:
    for port in (8000, 8080):
        with urlopen(f"http://127.0.0.1:{port}/api/health/ready", timeout=15) as response:
            health = json.load(response)
        assert health["status"] == "ok", "Dependency readiness failed"
        assert health["dependencies"] == {
            "postgresql": "ok",
            "redis": "ok",
            "schema": "ok",
        }
        print(f"PASS live readiness on :{port}", flush=True)
    output = docker(
        "exec",
        "-T",
        "worker",
        "celery",
        "-A",
        "app.workers.celery_app:celery_app",
        "inspect",
        "ping",
        "--timeout",
        "10",
    )
    assert "pong" in output, "Worker did not respond"
    print("PASS Celery worker ping", flush=True)

    config = dotenv_values(ROOT / ".env")
    database_url = config.get("DATABASE_URL")
    redis_url = config.get("REDIS_URL")
    if not database_url or not redis_url:
        raise RuntimeError("The verifier requires DATABASE_URL and REDIS_URL in .env")
    database = make_url(database_url).set(host=address("postgres"))
    redis = make_url(redis_url).set(host=address("redis"))
    name = "cisrice_verify_" + uuid4().hex
    environment = dict(os.environ)
    environment.update(
        DATABASE_URL=database.set(database=name).render_as_string(hide_password=False),
        REDIS_URL=redis.render_as_string(hide_password=False),
        CISRICE_INTEGRATION="1",
    )

    def run(*args: str) -> None:
        subprocess.run(
            [sys.executable, "-m", *args],
            cwd=ROOT / "backend",
            env=environment,
            stdin=subprocess.DEVNULL,
            check=True,
            timeout=120,
        )

    with psycopg.connect(
        host=database.host,
        port=database.port or 5432,
        user=database.username,
        password=database.password,
        dbname=database.database,
        autocommit=True,
        connect_timeout=5,
    ) as admin:
        admin.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(name)))
        print("Created isolated verification database", flush=True)
        try:
            run("alembic", "upgrade", "head")
            run("alembic", "check")
            run("pytest", "tests", "-q")
            run("alembic", "downgrade", "base")
            with psycopg.connect(
                host=database.host,
                port=database.port or 5432,
                user=database.username,
                password=database.password,
                dbname=name,
                connect_timeout=5,
            ) as check:
                row = check.execute("SELECT to_regclass('public.system_records')").fetchone()
                assert row is not None and row[0] is None
            run("alembic", "upgrade", "head")
            run("alembic", "check")
            run("pytest", "tests/test_services.py", "-q")
            print("PASS real-service tests and migration round trip", flush=True)
        finally:
            admin.execute(sql.SQL("DROP DATABASE {}").format(sql.Identifier(name)))
            print("Removed only the disposable verification database", flush=True)


if __name__ == "__main__":
    main()
