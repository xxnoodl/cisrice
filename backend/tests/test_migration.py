import sys
from pathlib import Path
from subprocess import run


def test_offline_migration_generates_postgres_schema() -> None:
    backend = Path(__file__).resolve().parents[1]
    result = run(
        [sys.executable, "-m", "alembic", "upgrade", "head", "--sql"],
        cwd=backend,
        capture_output=True,
        text=True,
        timeout=30,
        check=True,
    )
    assert "CREATE TABLE system_records" in result.stdout
    assert "TIMESTAMP WITH TIME ZONE" in result.stdout
    assert "UNIQUE (name)" in result.stdout
    assert "0001" in result.stdout
