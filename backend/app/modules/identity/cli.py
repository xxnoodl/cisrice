"""Local operator user provisioning; no public sign-up or default password."""

import argparse
import getpass
from uuid import uuid4

from pydantic import SecretStr, ValidationError
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.core.database import make_engine
from app.core.security import password_hash
from app.modules.identity.models import User
from app.modules.identity.repository import IdentityRepository
from app.modules.identity.schemas import Login
from app.modules.identity.service import IdentityService


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Create a local Cisrice user (operator access required)"
    )
    parser.add_argument("command", choices=["create-user"])
    parser.add_argument("--email", required=True)
    args = parser.parse_args()
    password = getpass.getpass("Password (12–1024 characters): ")
    confirm = getpass.getpass("Confirm password: ")
    if password != confirm:
        parser.error("Passwords do not match")
    try:
        data = Login(email=args.email, password=SecretStr(password))
    except ValidationError:
        parser.error("Provide a valid email and a password between 12 and 1024 characters")
    settings = Settings()
    engine = make_engine(settings)
    try:
        with Session(engine) as db, db.begin():
            # Serializes duplicate-email checks during concurrent operator setup.
            db.execute(text("SELECT pg_advisory_xact_lock(61392001)"))
            repo = IdentityRepository(db)
            if repo.user_by_email(data.email):
                parser.error("A user with that email already exists")
            user = repo.save(User(email=data.email, password_hash=password_hash(password)))
            IdentityService(repo, settings, str(uuid4())).record(user, "user.created", user.id)
        print("User created. Sign in through the localhost dashboard.")
    finally:
        engine.dispose()


if __name__ == "__main__":
    main()
