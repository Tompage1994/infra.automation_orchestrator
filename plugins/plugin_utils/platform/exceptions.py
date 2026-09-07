# -*- coding: utf-8 -*-

# Copyright: (c) 2026, Tom Page <tpage@redhat.com>
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

"""Error taxonomy for the Automation Orchestrator platform SDK.

Mirrors the class names and shape of ``ansible.platform``'s exception
hierarchy so the two collections can share error-handling logic if they are
consolidated later.
"""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

import logging
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


class AOError(Exception):
    """Base exception for all Automation Orchestrator SDK errors."""

    def __init__(self, message: str, operation: Optional[str] = None, resource: Optional[str] = None, details: Optional[Dict[str, Any]] = None):
        super().__init__(message)
        self.message = message
        self.operation = operation
        self.resource = resource
        self.details = details or {}
        self.retryable = False

    def __str__(self) -> str:
        parts = [self.message]
        if self.operation:
            parts.append(f"Operation: {self.operation}")
        if self.resource:
            parts.append(f"Resource: {self.resource}")
        return " | ".join(parts)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "error_type": self.__class__.__name__,
            "message": self.message,
            "operation": self.operation,
            "resource": self.resource,
            "details": self.details,
        }


class AuthenticationError(AOError):
    """Raised for invalid credentials, expired tokens, or 401/403 on auth endpoints."""

    def __init__(self, message: str, operation: Optional[str] = None, resource: Optional[str] = None, details: Optional[Dict[str, Any]] = None):
        super().__init__(message, operation, resource, details)
        self.retryable = False

    def get_suggestion(self) -> str:
        lowered = self.message.lower()
        if "token" in lowered or "expired" in lowered:
            return "Check if the token has expired. Provide a valid ao_token, or client_id/client_secret to allow automatic refresh."
        if "password" in lowered or "username" in lowered:
            return "Verify ao_username and ao_password are correct."
        return "Check that ao_token, ao_username/ao_password, or ao_client_id/ao_client_secret are valid and have proper permissions."


class NetworkError(AOError):
    """Raised for connection timeouts, DNS failures, refused connections, or SSL errors."""

    def __init__(
        self,
        message: str,
        operation: Optional[str] = None,
        resource: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
        original_exception: Optional[Exception] = None,
    ):
        super().__init__(message, operation, resource, details)
        self.retryable = True
        self.original_exception = original_exception

    def get_suggestion(self) -> str:
        lowered = self.message.lower()
        if "timeout" in lowered:
            return "Check network connectivity and AO availability. Consider increasing ao_request_timeout."
        if "connection" in lowered or "refused" in lowered:
            return "Verify ao_host is correct and the Automation Orchestrator service is running."
        if "dns" in lowered or "resolve" in lowered:
            return "Check DNS resolution for the ao_host hostname."
        if "ssl" in lowered or "tls" in lowered:
            return "Verify the SSL certificate is valid. Use ao_validate_certs=false for testing only."
        return "Check network connectivity and AO availability."


class ValidationError(AOError):
    """Raised for invalid input parameters, missing required fields, or constraint violations."""

    def __init__(
        self,
        message: str,
        operation: Optional[str] = None,
        resource: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
        invalid_fields: Optional[list] = None,
    ):
        super().__init__(message, operation, resource, details)
        self.retryable = False
        self.invalid_fields = invalid_fields or []

    def get_suggestion(self) -> str:
        if self.invalid_fields:
            return f"Check the following fields are valid: {', '.join(self.invalid_fields)}"
        return "Review input parameters and ensure all required fields are provided with valid values."


class APIError(AOError):
    """Raised for HTTP 4xx/5xx responses from the AO API.

    ``retryable`` is derived from ``status_code``: 5xx, 408, and 429 are
    retryable; other 4xx errors are not.
    """

    def __init__(
        self,
        message: str,
        operation: Optional[str] = None,
        resource: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
        status_code: Optional[int] = None,
        response_body: Optional[Dict[str, Any]] = None,
    ):
        super().__init__(message, operation, resource, details)
        self.status_code = status_code
        self.response_body = response_body or {}
        self.retryable = bool(status_code) and (status_code >= 500 or status_code in (408, 429))

    def get_suggestion(self) -> str:
        if self.status_code == 401:
            return "Authentication failed. Check credentials are valid and have proper permissions."
        if self.status_code == 403:
            return "Access forbidden. Check the user/service account has the required permissions."
        if self.status_code == 404:
            return "Resource not found. Verify the resource exists or check the identifier."
        if self.status_code == 409:
            return "Conflict. The resource may already exist or be in use."
        if self.status_code == 422:
            return "Validation error. Check input parameters and required fields."
        if self.status_code == 429:
            return "Rate limit exceeded. Wait before retrying or reduce request frequency."
        if self.status_code and self.status_code >= 500:
            return "Server error. This may be temporary. Retry the operation."
        return "Check the API response for details and verify input parameters."


class TimeoutError(AOError):  # noqa: A001 - intentionally shadows builtin, matches ansible.platform naming
    """Raised when a request or a polling operation (e.g. execution wait) times out."""

    def __init__(
        self,
        message: str,
        operation: Optional[str] = None,
        resource: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
        timeout_seconds: Optional[float] = None,
    ):
        super().__init__(message, operation, resource, details)
        self.retryable = True
        self.timeout_seconds = timeout_seconds

    def get_suggestion(self) -> str:
        if self.timeout_seconds:
            return f"Operation timed out after {self.timeout_seconds}s. Consider increasing ao_request_timeout or the module's timeout parameter."
        return "Operation timed out. Consider increasing ao_request_timeout or the module's timeout parameter."


def classify_exception(exception: Exception, operation: Optional[str] = None, resource: Optional[str] = None) -> AOError:
    """Classify a generic exception raised by the HTTP layer into the AO error taxonomy."""
    if isinstance(exception, AOError):
        return exception

    from ansible.module_utils.six.moves.urllib.error import HTTPError, URLError
    from ansible.module_utils.urls import ConnectionError as AnsibleConnectionError
    from ansible.module_utils.urls import SSLValidationError

    if isinstance(exception, HTTPError):
        status_code = exception.code
        return APIError(
            message=f"API request failed: HTTP {status_code}",
            operation=operation,
            resource=resource,
            details={"status_code": status_code},
            status_code=status_code,
        )

    if isinstance(exception, SSLValidationError):
        return NetworkError(
            message=f"SSL error: {exception}",
            operation=operation,
            resource=resource,
            details={"original_exception": str(exception), "error_type": "ssl"},
            original_exception=exception,
        )

    if isinstance(exception, (AnsibleConnectionError, URLError)):
        return NetworkError(
            message=f"Connection error: {exception}",
            operation=operation,
            resource=resource,
            details={"original_exception": str(exception)},
            original_exception=exception,
        )

    if isinstance(exception, ValueError) and ("auth" in str(exception).lower() or "credential" in str(exception).lower()):
        return AuthenticationError(message=f"Authentication error: {exception}", operation=operation, resource=resource, details={"original_exception": str(exception)})

    if isinstance(exception, ValueError):
        return ValidationError(message=f"Validation error: {exception}", operation=operation, resource=resource, details={"original_exception": str(exception)})

    return AOError(
        message=f"Unexpected error: {exception}",
        operation=operation,
        resource=resource,
        details={"original_exception": str(exception), "exception_type": type(exception).__name__},
    )
