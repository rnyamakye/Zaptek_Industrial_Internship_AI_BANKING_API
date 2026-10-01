"""Basic audit logging. One line per security-relevant event; never log passwords or tokens."""
import logging

_logger = logging.getLogger("audit")


def audit(event: str, **fields) -> None:
    details = " ".join(f"{k}={v}" for k, v in fields.items())
    _logger.info("AUDIT %s %s", event, details)
