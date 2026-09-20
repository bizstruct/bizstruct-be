from datetime import datetime, timedelta, timezone
from uuid import UUID
from pydantic import ValidationError
import jwt
from pwdlib import PasswordHash
from pwdlib.hashers.argon2 import Argon2Hasher

from app.core.config import settings
from app.exceptions.auth import InvalidTokenError, TokenExpiredError
from app.schemas.auth import TokenPayload


password_hash = PasswordHash((Argon2Hasher(),))


def hash_password(password: str) -> str:
    """
        Hashes a plaintext password using Argon2.

        Args:
            password (str): The plaintext password to hash.

        Returns:
            str: The hashed password.
    """
    return password_hash.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """
        Verifies a plaintext password against a hashed password.

        Args:
            plain_password (str): The plaintext password to verify.
            hashed_password (str): The hashed password to compare against.

        Returns:
            bool: True if the passwords match, False otherwise.
    """
    return password_hash.verify(plain_password, hashed_password)


def create_token(
    user_id: UUID,
    token_type: str,
    expires_delta: timedelta,
) -> str:
    """
        Encodes a JWT token with the standard claims (sub, type, iat, exp).
    """
    now = datetime.now(timezone.utc)
    token_payload = TokenPayload(
        sub=user_id,
        type=token_type,
        iat=int(now.timestamp()),
        exp=int((now + expires_delta).timestamp()),
    )
    return jwt.encode(
        token_payload.model_dump(mode="json"),
        settings.jwt.secret_key,
        algorithm=settings.jwt.algorithm,
    )


def create_access_token(user_id: UUID) -> str:
    """
        Generates a short-lived access token.
    """
    return create_token(
        user_id=user_id,
        token_type="access",
        expires_delta=timedelta(seconds=settings.jwt.access_token_expire_seconds),
    )

def create_refresh_token(user_id: UUID) -> str:
    """
        Generates a long-lived refresh token.
    """
    return create_token(
        user_id=user_id,
        token_type="refresh",
        expires_delta=timedelta(seconds=settings.jwt.refresh_token_expire_seconds),
    )


def decode_token(token: str, expected_type: str) -> TokenPayload:
    """
        Decodes and validates a JWT token and its expected payload type.

        Raises:
            TokenExpiredError: If the token has expired.
            InvalidTokenError: If signature, format, or type claim is invalid.
    """
    try:
        raw_payload = jwt.decode(
            token,
            settings.jwt.secret_key,
            algorithms=[settings.jwt.algorithm],
        )
    except jwt.ExpiredSignatureError as err:
        raise TokenExpiredError() from err
    except jwt.PyJWTError as err:
        raise InvalidTokenError() from err

    try:
        payload = TokenPayload.model_validate(raw_payload)
    except ValidationError as err:
        raise InvalidTokenError("Malformed token payload") from err
    
    if payload.type != expected_type:
        raise InvalidTokenError(f"Expected {expected_type} token, got {payload.type}")

    return payload

