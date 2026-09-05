import json
import logging
import sys
from datetime import datetime, timezone

from app.core.request_context import get_request_id


class RequestIdFilter(logging.Filter):
    """Attaches the current request's ID (see request_context.py) to every
    log record, so it's available to the formatter below — including for
    log lines emitted deep inside a helper function that has no idea
    it's running inside an HTTP request at all."""

    def filter(self, record: logging.LogRecord) -> bool:
        record.request_id = get_request_id()
        return True


class JsonFormatter(logging.Formatter):
    """
    Plain stdlib logging, formatted as one JSON object per line. No new
    dependency (e.g. python-json-logger) needed for this — the format is
    simple enough to hand-roll, and hosting platforms (Railway, Render,
    Vercel, or anything reading stdout) all handle line-delimited JSON
    logs natively, making them searchable/filterable by field instead of
    grep-ing free text.

    The specific goal from the roadmap this exists for: "structured
    logging with request IDs so you can trace one request across
    frontend -> backend -> DB." What this actually delivers is the
    backend half of that chain — every log line this process emits while
    handling a request carries the same `request_id`, so filtering server
    logs by that one value reconstructs everything the backend did for
    it. The frontend half is `apiClient.ts` generating that ID and
    sending it as `X-Request-ID`; the "-> DB" half is honestly weaker —
    we're not tagging raw Postgres query logs with it (that needs
    server-side log configuration on whatever's hosting Postgres, e.g.
    Supabase's own log_line_prefix, which is out of this app's control),
    so a DB-side slow query still has to be correlated by timestamp, not
    request_id, until that's set up separately.
    """

    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "request_id": getattr(record, "request_id", "-"),
        }
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        return json.dumps(payload)


def setup_logging(level: str = "INFO") -> None:
    """
    Called once, at import time, from main.py — before the app object
    (or anything that might log) is even constructed.

    Replaces the root logger's handlers rather than adding to them, so
    calling this more than once (e.g. accidentally, or in a test fixture)
    doesn't result in every log line being printed twice.
    """
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonFormatter())
    handler.addFilter(RequestIdFilter())

    root = logging.getLogger()
    root.handlers = [handler]
    root.setLevel(level.upper())

    # uvicorn's own loggers otherwise print their own plain-text format
    # side by side with our JSON lines — route them through the same
    # JSON handler so log output is consistent no matter which module
    # emitted it.
    for noisy_logger in ("uvicorn", "uvicorn.error", "uvicorn.access"):
        logging.getLogger(noisy_logger).handlers = [handler]
        logging.getLogger(noisy_logger).propagate = False
