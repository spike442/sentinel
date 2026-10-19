import logging
from collections.abc import Iterable

from sentinel.core.secrets import redact


class RedactingFilter(logging.Filter):
    def __init__(self, secrets: Iterable[str]):
        super().__init__()
        self.secrets = tuple(secret for secret in secrets if secret)

    def filter(self, record: logging.LogRecord) -> bool:
        message = record.getMessage()
        redacted = redact(message, self.secrets)
        if redacted != message:
            record.msg, record.args = redacted, ()
        return True


def configure_logging(level: str) -> None:
    resolved_level = level.upper()
    logging.basicConfig(level=resolved_level, format="%(asctime)s %(levelname)s %(name)s %(message)s", force=True)


def redact_logged_secrets(logger_name: str, secrets: Iterable[str]) -> None:
    secret_filter = RedactingFilter(secrets)
    target = logging.getLogger(logger_name)
    target.addFilter(secret_filter)
