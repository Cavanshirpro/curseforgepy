"""
exceptions.py

Centralized custom exception types for the library.

This file defines a small hierarchy of exceptions used across the client,
downloader, installer and dataType modules. Each error carries an optional
numeric code and optional raw response object for easier debugging.
"""

from typing import Optional, Any


class CurseForgeError(Exception):
    """
    Base class for all library-specific exceptions.

    Attributes
    ----------
    message: str
        Human readable error message.
    code: Optional[int]
        HTTP status code or internal error code if applicable.
    response: Optional[Any]
        Raw response object (requests.Response or API payload) for debugging.
    """

    def __init__(self, message: str, code: Optional[int] = None, response: Optional[Any] = None):
        self.message = message
        self.code = code
        self.response = response
        # call base with a string representation so exceptions print nicely
        super().__init__(self.__str__())

    def __str__(self) -> str:
        base = f"[CurseForgeError] {self.message}"
        if self.code is not None:
            base += f" (code={self.code})"
        return base

    def __repr__(self) -> str:
        return f"<{self.__class__.__name__} code={self.code!r} message={self.message!r}>"

class BadRequestError(CurseForgeError):
    """HTTP 400 - Client sent invalid data (bad parameters / payload)."""


class UnauthorizedError(CurseForgeError):
    """HTTP 401 - Missing or invalid API credentials (x-api-key)."""


class ForbiddenError(CurseForgeError):
    """HTTP 403 - Authenticated but not allowed to access resource."""


class AuthError(CurseForgeError):
    """
    General authentication/authorization error.

    This is a more generic class. Prefer raising UnauthorizedError/ForbiddenError
    for specific HTTP codes, but AuthError is useful for non-HTTP auth failures.
    """


class NotFoundError(CurseForgeError):
    """HTTP 404 - Requested resource not found."""


class RateLimitError(CurseForgeError):
    """HTTP 429 - Rate limit exceeded."""


class ServerError(CurseForgeError):
    """5xx - Server-side error from the API."""


class NetworkError(CurseForgeError):
    """Network / transport related error (timeouts, connection failures)."""


class InvalidResponseError(CurseForgeError):
    """Raised when the API returns malformed/unparseable data."""


class UnsupportedEndpointError(CurseForgeError):
    """Raised when a requested endpoint/key is not supported by CURSEFORGEAPIURLS."""


class MissingParameterError(CurseForgeError):
    """Raised when required path/query parameters are missing."""


class DownloadError(CurseForgeError):
    """Raised for downloadable file-related errors (I/O, remote 4xx/5xx during streaming)."""

class DataValidationError(CurseForgeError):
    """Raised when API payload does not match expected shape."""


class ConversionError(CurseForgeError):
    """Raised when converting between internal types fails."""


class ConfigurationError(CurseForgeError):
    """Raised when client/configuration is invalid or incomplete."""


class DependencyError(CurseForgeError):
    """Raised when an optional dependency (eg. tqdm) is missing but required."""


class OperationNotSupportedError(CurseForgeError):
    """Raised when a requested operation is not implemented for this API version."""

class ManifestError(CurseForgeError):
    """
    Raised when parsing/reading a modpack manifest fails.

    Use this in installer / manifest-parsing code paths to provide a clear,
    domain-specific exception.
    """

def map_http_status(status_code: int, message: str = "", response: Optional[Any] = None) -> CurseForgeError:
    """
    Convert an HTTP status code + message into an appropriate CurseForgeError instance.

    Parameters
    ----------
    status_code : int
        HTTP status code returned by the server.
    message : str
        Response text or short explanation.
    response : Any
        Raw response object (optional) to attach to the exception instance.

    Returns
    -------
    CurseForgeError
        An instance of a subclass representing the status.
    """
    if status_code == 400:
        return BadRequestError(message or "Bad Request", status_code, response)
    if status_code == 401:
        return UnauthorizedError(message or "Unauthorized", status_code, response)
    if status_code == 403:
        return ForbiddenError(message or "Forbidden", status_code, response)
    if status_code == 404:
        return NotFoundError(message or "Not Found", status_code, response)
    if status_code == 429:
        return RateLimitError(message or "Rate Limited", status_code, response)
    if 500 <= status_code <= 599:
        return ServerError(message or "Server Error", status_code, response)
    # fallback
    return CurseForgeError(message or f"HTTP {status_code}", status_code, response)
