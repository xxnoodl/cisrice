import os

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import inspect

from app.core.config import Settings
from app.core.database import make_engine
from app.main import create_app


@pytest.mark.integration
@pytest.mark.skipif(os.getenv("CISRICE_INTEGRATION") != "1", reason="real services not enabled")
def test_real_services_and_migrated_schema() -> None:
    settings = Settings()
    with TestClient(create_app(settings)) as client:
        assert client.get("/api/health/ready").status_code == 200
    engine = make_engine(settings)
    try:
        assert "system_records" in inspect(engine).get_table_names()
    finally:
        engine.dispose()
