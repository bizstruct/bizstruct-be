from pydantic import BaseModel, Field


class ErrorResponse(BaseModel):
    """
        Standard error response payload.
    """
    detail: str = Field(
        ...,
        description="A human-readable description of the error",
        examples=["User with identifier '01920b7a-...' was not found"],
    )
    