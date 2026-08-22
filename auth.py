"""
User Authentication module supporting registration, password hashing, and session token verification.
"""

import hashlib
import secrets
from typing import Optional, Dict

# In-memory session token store (token -> user_id)
SESSIONS: Dict[str, str] = {}


def hash_password(password: str) -> str:
    """Generates a secure SHA-256 password hash."""
    return hashlib.sha256(password.encode('utf-8')).hexdigest()


def create_session(user_id: str) -> str:
    """Creates a new session token for a user."""
    token = secrets.token_hex(24)
    SESSIONS[token] = user_id
    return token


def get_user_id_from_token(token: Optional[str]) -> Optional[str]:
    """Retrieves user_id from session token."""
    if not token:
        return None
    return SESSIONS.get(token)


def revoke_session(token: str):
    """Revokes a session token (logout)."""
    if token in SESSIONS:
        del SESSIONS[token]
