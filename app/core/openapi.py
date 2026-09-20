from typing import Any

from fastapi import status

from app.schemas.common import ErrorResponse


def error_responses(*status_codes: int) -> dict[int | str, dict[str, Any]]:
    """
        Generate a dictionary of error responses for the given status codes.

        Args:
            *status_codes: HTTP status codes for which to generate error responses.
        Returns:
            A dictionary mapping status codes to their corresponding error response schemas.
        """
    return {
        code: {
            "model": ErrorResponse,
            "description": status.HTTP_STATUS_PHRASES.get(code, "Error"),
        }
        for code in status_codes
    }