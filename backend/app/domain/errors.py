"""Domain errors.

Adapters raise these instead of library errors. The interfaces layer turns each one
into a Bangla message for the user (see messages_bn.py).
"""


class DomainError(Exception):
    """Base class. `code` is the stable name used in API error JSON."""

    code = "DOMAIN_ERROR"


class InvalidPhone(DomainError):
    code = "INVALID_PHONE"


class NotFound(DomainError):
    code = "NOT_FOUND"


class RateLimited(DomainError):
    code = "RATE_LIMITED"


class LLMUnavailable(DomainError):
    code = "LLM_UNAVAILABLE"
