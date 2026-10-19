from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """
    Centralized app configuration.

    Every value here is read from environment variables (or a local .env file).
    Nothing is hardcoded, so the same code runs in local dev, staging, and
    production just by swapping the .env values / hosting platform's env vars.
    """

    environment: str = "development"

    # Supabase Postgres connection string, e.g.:
    # postgresql+asyncpg://postgres:PASSWORD@HOST:5432/postgres
    database_url: str

    # Upstash (or any) Redis connection string, e.g.:
    # redis://default:PASSWORD@HOST:6379
    redis_url: str

    # Used later (Phase 1) to verify Supabase-issued JWTs
    supabase_jwt_secret: str = ""

    # Needed to fetch Supabase's public signing keys (JWKS) for projects
    # using the newer asymmetric key scheme (ES256), e.g. https://xxxx.supabase.co
    supabase_url: str = ""

    # Supabase Dashboard -> Settings -> API -> "service_role" secret key.
    # ONLY ever used server-side (see core/supabase_admin.py) to create a
    # staff (manager/delivery) login on a shop owner's behalf — the one
    # place this app creates an account without the person signing
    # themselves up. Never sent to the frontend, never logged. Optional:
    # an empty value just means staff-account creation returns a clear
    # 500 instead of silently working, so local dev without this set
    # doesn't need to touch it unless that feature is actually used.
    supabase_service_role_key: str = ""

    # Which frontend origin(s) are allowed to call this API (CORS).
    # Comma-separated so staging and prod can be listed together, e.g.
    # "https://app.localmart.com,https://staging.localmart.com" — see
    # `cors_origins` below for the parsed form main.py actually uses.
    frontend_origin: str = "http://localhost:3000"

    # Phase 7 — observability & logging. Both optional: an empty
    # sentry_dsn means error tracking is simply off (see
    # core/observability.py), and log_level just controls verbosity.
    sentry_dsn: str = ""
    log_level: str = "INFO"

    # Sponsorship purchases (shop owner pays the PLATFORM for priority
    # placement). With the key pair set, checkout uses Razorpay; with it
    # empty AND environment != "production", checkout runs in a clearly
    # labelled TEST mode (no real money) so the flow can be exercised
    # locally. In production with no keys, buying is disabled (503).
    razorpay_key_id: str = ""
    razorpay_key_secret: str = ""
    # Razorpay Dashboard -> Webhooks (event: payment.captured) pointed at
    # POST /sponsorship/webhook. Safety net for a buyer who pays and then
    # closes the tab before the browser-side confirm call lands.
    razorpay_webhook_secret: str = ""

    # ---- Recommendations (see app/core/recommendations and
    # backend/docs/recommendations.md) ---------------------------------
    # Master kill switch: false => every /recommendations endpoint returns
    # an empty shelf (pages simply hide it) and events are not recorded.
    reco_enabled: bool = True
    # % of logged-in users (0-50) deterministically served the plain
    # "trending" baseline instead of the model — the control group that
    # lets the admin metrics prove the model actually lifts clicks/orders.
    reco_holdout_pct: int = 0
    # A product pair must have been bought by at least this many DISTINCT
    # customers to be recommended — blocks noise, single-buyer gaming and
    # leaking one person's purchases through a rare pairing.
    reco_min_co_buyers: int = 3
    # Purchases/wishlists lose half their weight every this many days.
    reco_half_life_days: int = 90
    # Per-customer cap on items used to build similarities (most recent /
    # strongest kept) so one heavy buyer can't dominate or blow up the job.
    reco_max_items_per_user: int = 50
    reco_neighbors_per_product: int = 30
    # Comma-separated shop/product categories that never take part in
    # cross-customer recommendations (health data is sensitive).
    reco_excluded_categories: str = "Pharmacy"
    # Raw impression/click rows older than this are deleted by the nightly job.
    reco_event_retention_days: int = 90
    # Hours after which /health/recommendations reports the model as stale.
    reco_stale_hours: int = 36
    # A new model run is only promoted if its hit-rate is at least
    # (1 - this) times the previous run's, and not below the popularity baseline.
    reco_max_regression: float = 0.2

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    @property
    def reco_excluded_category_list(self) -> list[str]:
        return [c.strip() for c in self.reco_excluded_categories.split(",") if c.strip()]

    @property
    def cors_origins(self) -> list[str]:
        """`frontend_origin` split on commas and trimmed — what
        CORSMiddleware actually wants (a list), while the env var itself
        stays a plain human-editable string."""
        return [origin.strip() for origin in self.frontend_origin.split(",") if origin.strip()]


# Imported everywhere else as: from app.core.config import settings
settings = Settings()
