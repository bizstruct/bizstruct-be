from datetime import datetime
from typing import Annotated
import uuid

from pydantic import (
    BaseModel,
    ConfigDict,
    EmailStr,
    Field,
    StringConstraints,
)

NormalizedEmail = Annotated[
    EmailStr,
    StringConstraints(strip_whitespace=True, to_lower=True),
]

RawPassword = Annotated[
    str,
    Field(min_length=8, max_length=128, strip_whitespace=True),
]


class UserBase(BaseModel):
    """
        Base model for shared user fields.
    """
    email: NormalizedEmail = Field(
        ...,
        description="User's email address",
        examples=["user@example.com"],
    )
    full_name: str | None = Field(
        default=None,
        description="User's full name",
        examples=["John Doe"],
    )


class UserCreate(UserBase):
    """
        Model for creating a new user.
    """
    password: RawPassword = Field(
        ...,
        description="Plaintext password to be hashed",
        examples=["securepassword123"],
    )
    is_service: bool = Field(
        default=False,
        description="Indicates if the user is a service account",
    )


class UserUpdate(BaseModel):
    """
        Model for updating user data.
    """
    email: NormalizedEmail | None = Field(
        default=None,
        description="New email address",
        examples=["newuser@example.com"],
    )
    full_name: str | None = Field(
        default=None,
        description="New full name",
        examples=["Jane Doe"],
    )
    password: RawPassword | None = Field(
        default=None,
        description="New plaintext password to be hashed",
        examples=["newsecurepassword456"],
    )
    is_active: bool | None = Field(
        default=None,
        description="Indicates if the user is active",
    )


class UserResponse(UserBase):
    """
        Model for user data returned in responses.
    """

    id: uuid.UUID = Field(
        ...,
        description="Unique identifier for the user",
        examples=["018d3c1a-8c7a-7b3c-9a1d-7b2a5f1e8c9a"],
    )
    is_active: bool = Field(
        ...,
        description="Indicates if the user is active",
    )
    is_service: bool = Field(
        ...,
        description="Indicates if the user is a service account",
    )
    created_at: datetime = Field(
        ...,
        description="Timestamp with timezone when the user was created",
    )
    updated_at: datetime | None = Field(
        default=None,
        description="Timestamp with timezone when the user was last updated",
    )

    model_config = ConfigDict(from_attributes=True)

