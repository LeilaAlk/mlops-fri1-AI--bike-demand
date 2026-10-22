"""Structured logs: one JSON line on stdout per request and per start-up event.

Only operational metadata is logged (ids, route, status, duration, identity).
Request bodies, headers and environment values are never logged.
"""

import json
import logging
import re
import sys
import time
import uuid
from collections.abc import Callable
from datetime import UTC, datetime

from fastapi import FastAPI, Request

logger = logging.getLogger("bike_demand.service")
REQUEST_ID_HEADER = "X-Request-ID"
# A caller-supplied id is reused only if it is short and harmless; else a new one.
SAFE_ID = re.compile(r"^[A-Za-z0-9_.-]{1,64}$")


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        event = {
            "ts": datetime.fromtimestamp(record.created, UTC).isoformat(),
            "level": record.levelname,
            "event": record.getMessage(),
            **getattr(record, "fields", {}),
        }
        return json.dumps(event, default=str)


def configure_logging(level: str = "INFO") -> None:
    if not any(isinstance(h.formatter, JsonFormatter) for h in logger.handlers):
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(JsonFormatter())
        logger.addHandler(handler)
    logger.setLevel(level)


def log_event(event: str, level: int = logging.INFO, **fields) -> None:
    logger.log(level, event, extra={"fields": fields})


def outcome(path: str, status: int) -> str:
    if status == 422:
        return "rejected"
    if status == 503:
        return "unavailable"
    if status >= 500:
        return "error"
    if path == "/predict" and status == 200:
        return "predicted"
    return "ok" if status < 400 else "client_error"


def install_request_logging(app: FastAPI, identity: Callable[[], dict]) -> None:
    """Log one line per request and return the request id to the caller."""

    @app.middleware("http")
    async def log_request(request: Request, call_next):
        supplied = request.headers.get(REQUEST_ID_HEADER, "")
        request_id = supplied if SAFE_ID.match(supplied) else uuid.uuid4().hex
        start = time.perf_counter()
        status = 500
        try:
            response = await call_next(request)
            status = response.status_code
            response.headers[REQUEST_ID_HEADER] = request_id
            return response
        finally:
            if status == 503:
                level = logging.WARNING  # not ready: expected, honest refusal
            elif status >= 500:
                level = logging.ERROR
            else:
                level = logging.INFO
            log_event(
                "request",
                level,
                request_id=request_id,
                method=request.method,
                path=request.url.path,
                status=status,
                outcome=outcome(request.url.path, status),
                duration_ms=round((time.perf_counter() - start) * 1000, 1),
                **identity(),
            )
