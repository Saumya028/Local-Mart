from contextvars import ContextVar

# One value per in-flight request, set by RequestIDMiddleware in main.py
# before the request reaches any route handler, and read back out by
# logging_config.py's logging.Filter so EVERY log line emitted while
# handling that request — from any module, at any depth — carries the
# same request_id, without threading it through every function signature
# by hand.
_request_id: ContextVar[str] = ContextVar("request_id", default="-")


def get_request_id() -> str:
    return _request_id.get()


def set_request_id(value: str) -> None:
    _request_id.set(value)
