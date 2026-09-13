"""Password and opaque bearer-session helpers."""

import base64
import hashlib
import hmac
import secrets


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    digest = hashlib.scrypt(password.encode(), salt=salt, n=2**14, r=8, p=1)
    return (
        "$scrypt$16384$8$1$"
        + base64.urlsafe_b64encode(salt).decode()
        + "$"
        + base64.urlsafe_b64encode(digest).decode()
    )


def verify_password(password: str, encoded: str) -> bool:
    try:
        parts = encoded.split("$")
        if len(parts) != 7 or parts[1] != "scrypt":
            return False
        _, _, n, r, p, salt, expected = parts
        if (int(n), int(r), int(p)) != (2**14, 8, 1):
            return False
        decoded_salt = base64.urlsafe_b64decode(salt)
        decoded_expected = base64.urlsafe_b64decode(expected)
        if len(decoded_salt) != 16 or len(decoded_expected) != 64:
            return False
        actual = hashlib.scrypt(
            password.encode(),
            salt=decoded_salt,
            n=int(n),
            r=int(r),
            p=int(p),
        )
        return hmac.compare_digest(actual, decoded_expected)
    except (ValueError, TypeError):
        return False


def new_session_token() -> str:
    return secrets.token_urlsafe(32)


def session_digest(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()
