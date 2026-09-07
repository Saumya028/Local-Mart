"""
Deliberately does NOT spin up a real Postgres/Redis or make live HTTP
calls through the app — see backend/README.md's "What this test suite
does and doesn't cover" for why, and what's still missing. This checks
the one thing that's cheap to check and has bitten real projects: does
the app even IMPORT and construct without blowing up, and is every
router actually registered (a router file existing doesn't mean
someone remembered the `app.include_router(...)` line in main.py).
"""
import app.main as main


def test_app_imports_and_constructs():
    assert main.app.title == "LocalMart API"


def test_openapi_schema_generates():
    # Exercises every route's response_model / dependency signature
    # enough to catch a broken Pydantic schema or a bad type hint that
    # would otherwise only surface the first time someone hits that
    # specific endpoint.
    schema = main.app.openapi()
    assert schema["paths"]


def test_every_router_is_registered():
    # Reads the OpenAPI schema's path keys rather than raw `app.routes`
    # objects — Starlette's internal route representation is not a
    # stable public API (it changed shape between minor versions during
    # this very hardening pass, breaking an earlier version of this
    # test), while the generated OpenAPI schema is the actual public
    # contract this app promises and is worth pinning a test to instead.
    schema = main.app.openapi()
    paths = set(schema["paths"].keys())
    expected_prefixes = [
        "/health",
        "/auth/me",
        "/categories",
        "/shops",
        "/products",
        "/cart",
        "/addresses",
        "/orders",
        "/dashboard",
        "/admin",
        "/webhooks/razorpay",
    ]
    for prefix in expected_prefixes:
        assert any(p == prefix or p.startswith(prefix) for p in paths), (
            f"no route found for {prefix} — was its router's app.include_router(...) "
            "call ever added to main.py?"
        )


def test_cors_locked_to_configured_origins_not_wildcard():
    # The specific regression this guards against: someone "temporarily"
    # switching allow_origins to ["*"] to debug a CORS issue locally,
    # then forgetting to revert it before merging.
    cors_middleware = next(
        m for m in main.app.user_middleware if m.cls.__name__ == "CORSMiddleware"
    )
    assert "*" not in cors_middleware.kwargs["allow_origins"]


def test_request_id_middleware_is_registered():
    assert any(m.cls.__name__ == "RequestIDMiddleware" for m in main.app.user_middleware)
