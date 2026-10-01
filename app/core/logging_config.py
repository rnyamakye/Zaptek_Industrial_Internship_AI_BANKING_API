"""Logging setup so audit events and AI prediction logs actually show up (uvicorn/Render only
configures its own loggers). Output goes to stdout, which Render collects."""
import logging


def setup_logging() -> None:
    # No-op if handlers already exist (e.g. under pytest).
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
