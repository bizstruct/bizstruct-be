from .base import AppException


class AuthenticationError(AppException):
    code: str = "authentication_failed"

    def __init__(self, message: str = "Invalid credentials") -> None:
        super().__init__(message)


class TokenExpiredError(AuthenticationError):
    code: str = "token_expired"

    def __init__(self, message: str = "Token has expired") -> None:
        super().__init__(message)


class InvalidTokenError(AuthenticationError):
    code: str = "invalid_token"

    def __init__(self, message: str = "Invalid token") -> None:
        super().__init__(message)


class PermissionDeniedError(AppException):
    code: str = "permission_denied"

    def __init__(
        self,
        message: str = "You do not have permission to perform this action",
    ) -> None:
        super().__init__(message)

