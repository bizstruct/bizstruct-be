from http import HTTPStatus
from typing import Any

from app.schemas.common import ErrorResponse


def error_responses(*status_codes: int) -> dict[int | str, dict[str, Any]]:
    """
        Generate a dictionary of error responses for the given status codes.

        Args:
            *status_codes: HTTP status codes for which to generate error responses.
        Returns:
            A dictionary mapping status codes to their corresponding error response schemas.
        """
    responses: dict[int | str, dict[str, Any]] = {}
    for code in status_codes:
        try:
            description = HTTPStatus(code).phrase
        except ValueError:
            description = "Error"

        responses[code] = {
            "model": ErrorResponse,
            "description": description,
        }
    return responses