from sqlalchemy import text
from sqlalchemy.engine import Engine


class HealthRepository:
    def __init__(self, engine: Engine) -> None:
        self.engine = engine

    def ping(self) -> None:
        with self.engine.connect() as connection:
            connection.execute(text("SELECT 1"))

    def schema_ready(self) -> bool:
        with self.engine.connect() as connection:
            return connection.execute(text("SELECT version_num FROM alembic_version")).scalar() == (
                "0002"
            )
