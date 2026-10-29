"""Run schema migrations with operator credentials and grant a restricted runtime role."""

import os

import psycopg
from alembic import command
from alembic.config import Config
from psycopg import sql
from sqlalchemy.engine import make_url

from app.core.config import Settings


def main() -> None:
    password = os.environ.get("APP_DATABASE_PASSWORD", "")
    if len(password) < 24:
        raise RuntimeError("APP_DATABASE_PASSWORD must contain at least 24 characters")
    url = make_url(Settings().database_url)
    command.upgrade(Config("alembic.ini"), "head")
    with psycopg.connect(
        host=url.host,
        port=url.port or 5432,
        user=url.username,
        password=url.password,
        dbname=url.database,
        autocommit=True,
    ) as connection:
        role = sql.Identifier("cisrice_app")
        exists = connection.execute(
            "SELECT 1 FROM pg_roles WHERE rolname = %s", ("cisrice_app",)
        ).fetchone()
        if not exists:
            connection.execute(sql.SQL("CREATE ROLE {}").format(role))
        # SQL composition quotes password and identifiers; neither is logged by this runner.
        connection.execute(
            sql.SQL(
                "ALTER ROLE {} LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE "
                "NOREPLICATION NOBYPASSRLS PASSWORD {}"
            ).format(role, sql.Literal(password))
        )
        connection.execute(
            sql.SQL("GRANT CONNECT ON DATABASE {} TO {}").format(
                sql.Identifier(str(url.database)), role
            )
        )
        connection.execute("REVOKE CREATE ON SCHEMA public FROM PUBLIC")
        connection.execute(sql.SQL("REVOKE ALL ON SCHEMA public FROM {}").format(role))
        connection.execute(sql.SQL("GRANT USAGE ON SCHEMA public TO {}").format(role))
        connection.execute(
            sql.SQL("REVOKE ALL ON ALL TABLES IN SCHEMA public FROM {}").format(role)
        )
        tables = connection.execute(
            "SELECT tablename FROM pg_tables WHERE schemaname = 'public'"
        ).fetchall()
        for (table,) in tables:
            privilege = (
                "SELECT"
                if table in {"alembic_version", "system_records"}
                else (
                    "SELECT, INSERT"
                    if table in {"audit_events", "media_objects", "brand_assets"}
                    else "SELECT, INSERT, UPDATE"
                    if table in {"durable_jobs", "rights_decisions"}
                    else "SELECT, INSERT, UPDATE, DELETE"
                )
            )
            connection.execute(
                sql.SQL("GRANT " + privilege + " ON {} TO {}").format(
                    sql.Identifier("public", table), role
                )
            )
    print("Migrations applied and restricted runtime database role granted.")


if __name__ == "__main__":
    main()
