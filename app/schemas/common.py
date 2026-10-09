from pydantic import BaseModel, ConfigDict, Field
from pydantic.alias_generators import to_camel


class ErrorResponse(BaseModel):
    """
        Standard error response payload.
    """
    detail: str = Field(
        ...,
        description="A human-readable description of the error",
        examples=["User with identifier '01920b7a-...' was not found"],
    )
    

class CamelModel(BaseModel):
    """
        Base for public DTOs: camelCase on the wire, snake_case in Python.

        Only the outer DTO fields are camelCase; nested domain models
        (artifacts, consistency reports, failures) stay snake_case.
    """
    model_config = ConfigDict(
        alias_generator=to_camel,
        populate_by_name=True,
        from_attributes=True,
        extra="forbid",
    )
