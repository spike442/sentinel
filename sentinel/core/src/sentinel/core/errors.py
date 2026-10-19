"""Expected domain errors whose messages are safe to show operators.

The API maps these, and only these, to client errors. Any other exception, including
``ValueError`` or ``KeyError`` raised by a bug or a library, stays a 500 without leaking its text.
"""


class SentinelError(Exception):
    pass


class NotFound(SentinelError):
    pass


class Conflict(SentinelError):
    pass
