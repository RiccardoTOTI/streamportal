"""Error management system for StreamPortal API."""

from typing import Any, Optional, Union

from fastapi import HTTPException

from .logger import get_logger

logger = get_logger("errors")

class StreamPortalError(Exception):
    """Base exception for StreamPortal API."""

    def __init__(
        self,
        message: str,
        error_code: str = "INTERNAL_ERROR",
        status_code: int = 500,
        details: Optional[dict[str, Any]] = None,
    ) -> None:
        """Initialize StreamPortalError.

        Args:
            message: Error message
            error_code: Error code identifier
            status_code: HTTP status code
            details: Additional error details
        """
        self.message = message
        self.error_code = error_code
        self.status_code = status_code
        self.details = details or {}
        super().__init__(self.message)

class ValidationError(StreamPortalError):
    """Validation error for invalid input data."""

    def __init__(
        self,
        message: str,
        field: Optional[str] = None,
        details: Optional[dict[str, Any]] = None,
    ) -> None:
        """Initialize ValidationError.

        Args:
            message: Error message
            field: Field that failed validation
            details: Additional validation details
        """
        super().__init__(
            message=message,
            error_code="VALIDATION_ERROR",
            status_code=400,
            details={"field": field, **(details or {})},
        )

class AuthenticationError(StreamPortalError):
    """Authentication error for API key issues."""

    def __init__(
        self,
        message: str = "Authentication failed",
        details: Optional[dict[str, Any]] = None,
    ) -> None:
        """Initialize AuthenticationError.

        Args:
            message: Error message
            details: Additional authentication details
        """
        super().__init__(
            message=message,
            error_code="AUTHENTICATION_ERROR",
            status_code=401,
            details=details or {},
        )

class RateLimitError(StreamPortalError):
    """Rate limiting error."""

    def __init__(
        self, message: str = "Rate limit exceeded", retry_after: int = 60
    ) -> None:
        """Initialize RateLimitError.

        Args:
            message: Error message
            retry_after: Seconds to wait before retrying
        """
        super().__init__(
            message=message,
            error_code="RATE_LIMIT_ERROR",
            status_code=429,
            details={"retry_after": retry_after},
        )

class ExternalAPIError(StreamPortalError):
    """Error from external API calls."""

    def __init__(self, message: str, api_name: str, status_code: int = 502) -> None:
        """Initialize ExternalAPIError.

        Args:
            message: Error message
            api_name: Name of the external API
            status_code: HTTP status code
        """
        super().__init__(
            message=message,
            error_code="EXTERNAL_API_ERROR",
            status_code=status_code,
            details={"api_name": api_name},
        )

class NotFoundError(StreamPortalError):
    """Resource not found error."""

    def __init__(
        self,
        message: str,
        resource_type: Optional[str] = None,
        resource_id: Optional[Union[str, int]] = None,
    ) -> None:
        """Initialize NotFoundError.

        Args:
            message: Error message
            resource_type: Type of resource not found
            resource_id: ID of resource not found
        """
        super().__init__(
            message=message,
            error_code="NOT_FOUND_ERROR",
            status_code=404,
            details={"resource_type": resource_type, "resource_id": resource_id},
        )

class StreamingAvailabilityError(StreamPortalError):
    """Error related to streaming availability checks."""

    def __init__(
        self, message: str, content_id: Optional[Union[str, int]] = None
    ) -> None:
        """Initialize StreamingAvailabilityError.

        Args:
            message: Error message
            content_id: ID of content with streaming issues
        """
        super().__init__(
            message=message,
            error_code="STREAMING_AVAILABILITY_ERROR",
            status_code=503,
            details={"content_id": content_id},
        )

def handle_streamportal_error(error: StreamPortalError) -> dict[str, Any]:
    """Convert StreamPortal error to structured response."""
    error_response = {
        "error": {
            "code": error.error_code,
            "message": error.message,
            "status_code": error.status_code,
            "details": error.details,
        }
    }

    # Log the error
    logger.error(
        f"StreamPortal Error: {error.error_code} - {error.message}",
        extra_fields={
            "error_code": error.error_code,
            "status_code": error.status_code,
            "details": error.details,
        },
    )

    return error_response

def create_http_exception(error: StreamPortalError) -> HTTPException:
    """Convert StreamPortal error to FastAPI HTTPException."""
    return HTTPException(
        status_code=error.status_code,
        detail=handle_streamportal_error(error),
    )

def handle_generic_exception(
    exception: Exception, context: str = "Unknown"
) -> dict[str, Any]:
    """Handle generic exceptions and convert to structured error response."""
    error_response = {
        "error": {
            "code": "INTERNAL_ERROR",
            "message": "An unexpected error occurred",
            "status_code": 500,
            "details": {
                "context": context,
                "exception_type": type(exception).__name__,
            },
        }
    }

    # Log the exception with full traceback
    logger.exception(
        f"Unexpected error in {context}: {exception!s}",
        extra_fields={
            "context": context,
            "exception_type": type(exception).__name__,
            "exception_message": str(exception),
        },
    )

    return error_response

def validate_api_key(api_key: str) -> None:
    """Validate API key format and presence."""
    if not api_key:
        raise AuthenticationError("API key is required")

    if len(api_key) < 10:  # Basic validation
        raise AuthenticationError("Invalid API key format")

def validate_search_query(query: str) -> None:
    """Validate search query."""
    if not query or not query.strip():
        raise ValidationError("Search query cannot be empty", field="text_search")

    if len(query.strip()) < 2:
        raise ValidationError(
            "Search query must be at least 2 characters long", field="text_search"
        )

    if len(query) > 100:
        raise ValidationError(
            "Search query too long (max 100 characters)", field="text_search"
        )

def validate_content_id(content_id: int) -> None:
    """Validate content ID."""
    if not isinstance(content_id, int) or content_id <= 0:
        raise ValidationError(
            "Content ID must be a positive integer", field="content_id"
        )

def validate_content_type(content_type: str) -> None:
    """Validate content type."""
    allowed_types = ["Movie", "Series"]
    if content_type not in allowed_types:
        raise ValidationError(
            f"Content type must be one of: {', '.join(allowed_types)}",
            field="type_of_content",
        )

def log_api_request(
    method: str,
    path: str,
    client_ip: str,
    response_time: float,
    status_code: int,
    user_agent: Optional[str] = None,
) -> None:
    """Log API request details."""
    logger.info(
        f"API Request: {method} {path}",
        extra_fields={
            "method": method,
            "path": path,
            "client_ip": client_ip,
            "response_time": response_time,
            "status_code": status_code,
            "user_agent": user_agent,
        },
    )

def log_api_error(
    method: str,
    path: str,
    client_ip: str,
    error: Exception,
    user_agent: Optional[str] = None,
) -> None:
    """Log API error details."""
    logger.error(
        f"API Error: {method} {path} - {error!s}",
        extra_fields={
            "method": method,
            "path": path,
            "client_ip": client_ip,
            "error_type": type(error).__name__,
            "error_message": str(error),
            "user_agent": user_agent,
        },
    )
