import hashlib
import secrets

PROFILE_TOKEN_BYTES = 32


def generate_profile_token() -> str:
    """Return an opaque credential with 256 bits of entropy."""
    return secrets.token_urlsafe(PROFILE_TOKEN_BYTES)


def hash_profile_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()
