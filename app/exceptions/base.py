class AppException(Exception):
    """
        Base exception for all application-level errors.
    """

    def __init__(self, message: str = "An unexpected error occurred") -> None:
        super().__init__(message)
        self.message = message


class EntityNotFoundError(AppException):
    """
        Raised when a requested resource is not found in the database.
    """

    def __init__(self, entity_name: str, identifier: str | None = None) -> None:
        if identifier:
            message = f"{entity_name} with identifier '{identifier}' was not found"
        else:
            message = f"{entity_name} was not found"
        super().__init__(message)


class EntityAlreadyExistsError(AppException):
    """
        Raised when an entity with a unique field already exists.
    """

    def __init__(self, entity_name: str, field: str, value: str) -> None:
        message = f"{entity_name} with {field} '{value}' already exists"
        super().__init__(message)

