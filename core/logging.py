from __future__ import annotations

import logging

import structlog

# Adapted from ai-project-control-tower/app/core/logging.py (reused pattern,
# see BANKING_PLATFORM_INTEGRATION_PLAN.md §10: structlog was judged the
# stronger of the two logging approaches found in the audited repositories).
# Structured JSON output makes it straightforward to keep secrets/PII out of
# logs deliberately (never log raw settings objects or API keys — log field
# names, not values, when in doubt).

_CONFIGURED = False


def configure_logging(log_level: str = "INFO") -> None:
    global _CONFIGURED
    level = getattr(logging, log_level.upper(), logging.INFO)

    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.stdlib.add_log_level,
            structlog.stdlib.add_logger_name,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.stdlib.BoundLogger,
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )
    logging.basicConfig(format="%(message)s", level=level)
    _CONFIGURED = True


def get_logger(name: str) -> structlog.stdlib.BoundLogger:
    if not _CONFIGURED:
        configure_logging()
    return structlog.get_logger(name)
