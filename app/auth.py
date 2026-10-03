from __future__ import annotations
import hashlib, hmac, secrets
from dataclasses import dataclass

# Local demo users: no external credentials are required.
_USERS = {
    "admin": ("admin123", "admin"),
    "reviewer": ("reviewer123", "reviewer"),
    "agent": ("agent123", "agent"),
}

@dataclass
class User:
    username: str
    role: str
    session_token: str

def _hash(value: str, salt: bytes) -> str:
    return hashlib.pbkdf2_hmac("sha256", value.encode(), salt, 120_000).hex()

# Hash demo passwords at import time so passwords are never stored in the session.
_SALTS = {u: secrets.token_bytes(16) for u in _USERS}
_HASHES = {u: _hash(p, _SALTS[u]) for u, (p, _) in _USERS.items()}

def configured() -> bool:
    return True

def sign_in(username: str, password: str):
    username = username.strip().lower()
    if username not in _USERS:
        return None, "Invalid username or password."
    candidate = _hash(password, _SALTS[username])
    if not hmac.compare_digest(candidate, _HASHES[username]):
        return None, "Invalid username or password."
    return User(username, _USERS[username][1], secrets.token_urlsafe(24)), None
