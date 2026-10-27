from app.core.security import csrf_token, password_hash, token_digest, verify_password
from app.modules.identity.schemas import Login


def test_argon2id_hashes_and_verifies_without_storing_plaintext() -> None:
    password = "fixture-only-password"
    encoded = password_hash(password)
    assert encoded.startswith("$argon2id$")
    assert password not in encoded
    assert verify_password(encoded, password)
    assert not verify_password(encoded, "wrong fixture password")
    assert not verify_password("invalid hash", password)


def test_session_digest_and_csrf_are_different_and_session_specific() -> None:
    assert token_digest("token-a") != "token-a"
    assert csrf_token("token-a") != token_digest("token-a")
    assert csrf_token("token-a") != csrf_token("token-b")


def test_email_is_normalized_and_password_whitespace_is_preserved() -> None:
    data = Login.model_validate({"email": " USER@Example.test ", "password": "  long password  "})
    assert data.email == "user@example.test"
    assert data.password.get_secret_value() == "  long password  "
