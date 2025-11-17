"""Dashboard authentication and utilities."""

from datetime import datetime, timedelta
from typing import Optional

from jose import JWTError, jwt
from passlib.context import CryptContext

from .config import Settings

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a password against a hash."""
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password: str) -> str:
    """Hash a password."""
    return pwd_context.hash(password)


def create_access_token(data: dict, secret_key: str, expires_delta: Optional[timedelta] = None) -> str:
    """Create a JWT access token."""
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(hours=24)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, secret_key, algorithm="HS256")
    return encoded_jwt


def verify_token(token: str, secret_key: str) -> Optional[dict]:
    """Verify and decode a JWT token."""
    try:
        payload = jwt.decode(token, secret_key, algorithms=["HS256"])
        return payload
    except JWTError:
        return None


def authenticate_user(username: str, password: str, settings: Settings) -> bool:
    """Authenticate a user against settings.
    
    Supports both plain text (for backwards compatibility) and bcrypt hashed passwords.
    If the password in settings starts with $2b$ (bcrypt hash), it will be verified.
    Otherwise, plain text comparison is used.
    """
    if not settings.dashboard_username or not settings.dashboard_password:
        return False
    if username != settings.dashboard_username:
        return False
    
    stored_password = settings.dashboard_password
    
    # Check if password is hashed (bcrypt hashes start with $2b$)
    if stored_password.startswith("$2b$") or stored_password.startswith("$2a$"):
        # Verify against hashed password
        return verify_password(password, stored_password)
    else:
        # Plain text comparison (backwards compatibility)
        return password == stored_password

