"""Custom exception classes."""


class ReppyError(Exception):
    """Base exception for Reppy application."""

    def __init__(self, message: str, code: str = "INTERNAL_ERROR") -> None:
        self.message = message
        self.code = code
        super().__init__(message)


class AuthenticationError(ReppyError):
    """Raised when authentication fails."""

    def __init__(self, message: str = "Authentication failed") -> None:
        super().__init__(message, code="AUTHENTICATION_ERROR")


class AuthorizationError(ReppyError):
    """Raised when authorization fails."""

    def __init__(self, message: str = "Not authorized") -> None:
        super().__init__(message, code="AUTHORIZATION_ERROR")


class NotFoundError(ReppyError):
    """Raised when a resource is not found."""

    def __init__(self, resource: str = "Resource") -> None:
        super().__init__(f"{resource} not found", code="NOT_FOUND")


class ValidationError(ReppyError):
    """Raised when validation fails."""

    def __init__(self, message: str = "Validation failed") -> None:
        super().__init__(message, code="VALIDATION_ERROR")
