"""Logging configuration:
reference of logging configuration of uvicorn:
https://github.com/encode/uvicorn/blob/0.35.0/uvicorn/config.py#L68"""

import sys
from logging import Filter, LogRecord

# Define base log configuration
base_log_config: dict = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "simple_formatter": {
            "format": "%(name)-8s %(asctime)s - %(message)s",
            # Leaving datefmt string empty will result in the following timeformat:
            # 2023-08-24 13:45:42,774
            "datefmt": "",
        },
        "detailed_formatter": {
            "format": " %(name)-8s %(levelname)s: [%(asctime)s,%(msecs)03d  %(filename)s -> %(funcName)s(): line:%(lineno)s] - %(message)s",
            "datefmt": "%Y-%m-%d,%H:%M:%S",
        },
        "uvicorn_customized_formatter": {
            "()": "uvicorn.logging.DefaultFormatter",
            "format": "%(name)-8s %(levelprefix)s[%(asctime)s %(filename)s -> %(funcName)s(): line:%(lineno)s] - %(message)s",
        },
    },
    # Define handlers than can be used in loggers
    "handlers": {
        "stream_handler": {
            "class": "logging.StreamHandler",
            "formatter": "detailed_formatter",
            "stream": sys.stdout,
        },
        "uvicorn_error_handler": {
            "formatter": "uvicorn_customized_formatter",
            "class": "logging.StreamHandler",
            "stream": "ext://sys.stderr",
        },
        "uvicorn_access_handler": {
            "formatter": "uvicorn_customized_formatter",
            "class": "logging.StreamHandler",
            "stream": "ext://sys.stdout",
        },
    },
    # Root logger configuration
    "root": {
        "handlers": ["stream_handler"],
        "level": "INFO",
        "propagate": False,
    },
    "loggers": {
        "uvicorn.error": {
            "handlers": ["uvicorn_error_handler"],
            "level": "INFO",
            "propagate": False,
        },
        "uvicorn.access": {
            "handlers": ["uvicorn_access_handler"],
            "level": "INFO",
            "propagate": False,
        },
    },
}


class EndpointFilter(Filter):
    """Filter out logging from health check type endpoints."""

    def filter(self, record: LogRecord) -> bool:
        # Example log record with uvicorn.access log:
        # ('[IP ADDRESS]', 'GET', '/health/readiness', '1.1', 200)
        if (
            "/health/readiness" in record.args[2]
            or "/health/liveness" in record.args[2]
        ):
            return False
        return True
