"""Security utilities and middleware for StreamPortal API."""

import time

from fastapi import Request
from fastapi.responses import JSONResponse

from .errors import log_api_error, log_api_request
from .logger import get_logger

# Get logger instance
logger = get_logger("security")


class RateLimiter:
    """Simple in-memory rate limiter."""

    def __init__(self, requests_per_minute: int = 60) -> None:
        """Initialize RateLimiter.

        Args:
            requests_per_minute: Maximum requests allowed per minute
        """
        self.requests_per_minute = requests_per_minute
        self.requests: dict[str, list[float]] = {}
        logger.info(
            f"Rate limiter initialized with {requests_per_minute} requests per minute"
        )

    def is_allowed(self, client_ip: str) -> bool:
        """Check if request is allowed based on rate limit."""
        current_time = time.time()

        # Clean old requests (older than 1 minute)
        if client_ip in self.requests:
            self.requests[client_ip] = [
                req_time
                for req_time in self.requests[client_ip]
                if current_time - req_time < 60
            ]
        else:
            self.requests[client_ip] = []

        # Check if under limit
        if len(self.requests[client_ip]) >= self.requests_per_minute:
            logger.warning(
                f"Rate limit exceeded for IP: {client_ip}",
                extra_fields={
                    "client_ip": client_ip,
                    "request_count": len(self.requests[client_ip]),
                    "limit": self.requests_per_minute,
                },
            )
            return False

        # Add current request
        self.requests[client_ip].append(current_time)
        return True


# Global rate limiter instance
rate_limiter = RateLimiter(requests_per_minute=60)


async def rate_limit_middleware(request: Request, call_next):
    """Rate limiting middleware."""
    client_ip = get_client_ip(request)

    if not rate_limiter.is_allowed(client_ip):
        logger.warning(
            f"Rate limit exceeded for IP: {client_ip}",
            extra_fields={
                "client_ip": client_ip,
                "path": request.url.path,
                "method": request.method,
            },
        )
        return JSONResponse(
            status_code=429,
            content={
                "error": {
                    "code": "RATE_LIMIT_ERROR",
                    "message": "Too many requests. Please try again later.",
                    "status_code": 429,
                    "details": {"retry_after": 60},
                }
            },
        )

    response = await call_next(request)
    return response


def get_client_ip(request: Request) -> str:
    """Get client IP address, handling proxy headers."""
    # Check for forwarded headers (when behind proxy)
    forwarded_for = request.headers.get("X-Forwarded-For")
    if forwarded_for:
        return forwarded_for.split(",")[0].strip()

    # Check for real IP header
    real_ip = request.headers.get("X-Real-IP")
    if real_ip:
        return real_ip

    # Fallback to direct client IP
    return request.client.host


def validate_content_type(content_type: str) -> bool:
    """Validate content type for requests."""
    allowed_types = ["Movie", "Series"]
    return content_type in allowed_types


def sanitize_input(text: str) -> str:
    """Perform basic input sanitization."""
    if not text:
        return ""

    # Remove potentially dangerous characters
    dangerous_chars = ["<", ">", '"', "'", "&", "script", "javascript"]
    sanitized = text
    for char in dangerous_chars:
        sanitized = sanitized.replace(char, "")

    return sanitized.strip()


def log_request(request: Request, response_time: float) -> None:
    """Log request details for monitoring."""
    client_ip = get_client_ip(request)
    method = request.method
    path = request.url.path
    status_code = getattr(request, "status_code", 200)
    user_agent = request.headers.get("User-Agent", "Unknown")

    log_api_request(
        method=method,
        path=path,
        client_ip=client_ip,
        response_time=response_time,
        status_code=status_code,
        user_agent=user_agent,
    )


def log_error(request: Request, error: Exception) -> None:
    """Log error details for debugging."""
    client_ip = get_client_ip(request)
    method = request.method
    path = request.url.path
    user_agent = request.headers.get("User-Agent", "Unknown")

    log_api_error(
        method=method,
        path=path,
        client_ip=client_ip,
        error=error,
        user_agent=user_agent,
    )
