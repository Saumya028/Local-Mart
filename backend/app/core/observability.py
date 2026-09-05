import logging

from app.core.config import settings

logger = logging.getLogger(__name__)


def init_sentry() -> None:
    """
    Called once from main.py, before the FastAPI app is constructed.

    Deliberately a true no-op — not even an import of `sentry_sdk` — when
    `SENTRY_DSN` isn't set. That matters for local dev and for anyone
    running this project without a Sentry account at all: nothing here
    should require one. Once a real DSN is in the environment (staging/
    prod), this wires up automatic FastAPI + SQLAlchemy instrumentation
    (unhandled exceptions, slow spans) with no other code changes needed
    elsewhere in the app.

    `traces_sample_rate=0.1` sends performance traces for ~10% of
    requests rather than every single one — full tracing on 100% of
    traffic gets expensive fast on Sentry's pricing and isn't needed to
    spot systemic slowness; error reporting itself (via
    `main.py`'s exception handlers, decoupled from tracing) is unaffected
    by this and always captures every unhandled exception regardless of
    the sampling rate.
    """
    if not settings.sentry_dsn:
        return

    try:
        import sentry_sdk
        from sentry_sdk.integrations.fastapi import FastApiIntegration
        from sentry_sdk.integrations.sqlalchemy import SqlalchemyIntegration
    except ImportError:
        logger.warning(
            "SENTRY_DSN is set but the sentry-sdk package isn't installed — "
            "run `pip install -r requirements.txt` to enable error tracking."
        )
        return

    sentry_sdk.init(
        dsn=settings.sentry_dsn,
        environment=settings.environment,
        integrations=[FastApiIntegration(), SqlalchemyIntegration()],
        traces_sample_rate=0.1,
        send_default_pii=False,  # never attach cookies/request bodies by default — see README
    )
