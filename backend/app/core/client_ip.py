from fastapi import Request

from app.core.config import settings


def client_ip(request: Request) -> str:
    """
    The real client's IP, for per-IP rate limiting.

    Behind a reverse proxy / load balancer (Railway, Render, Fly, Heroku…)
    `request.client.host` is the PROXY's address, so every user would share
    one rate-limit bucket. The real address is in `X-Forwarded-For`, but
    that header is client-controlled up to the point a trusted proxy
    appends to it. So we trust only the entries our own proxies added:
    with TRUSTED_PROXY_COUNT=N, the real client is the Nth entry counting
    from the RIGHT (anything a client spoofed sits further left and is
    ignored). With N=0 (default) the header is ignored entirely.
    """
    peer = request.client.host if request.client else "unknown"
    n = settings.trusted_proxy_count
    if n <= 0:
        return peer
    parts = [p.strip() for p in request.headers.get("x-forwarded-for", "").split(",") if p.strip()]
    if len(parts) < n:
        return peer  # header missing/short: not actually behind N proxies
    return parts[-n]
