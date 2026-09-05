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

    # Which frontend origin(s) are allowed to call this API (CORS).
    # Comma-separated so staging and prod can be listed together, e.g.
    # "https://app.localmart.com,https://staging.localmart.com" — see
    # `cors_origins` below for the parsed form main.py actually uses.
    frontend_origin: str = "http://localhost:3000"

    # Razorpay test-mode keys (Razorpay Dashboard -> Settings -> API Keys)
    razorpay_key_id: str = ""
    razorpay_key_secret: str = ""
    # From Razorpay Dashboard -> Settings -> Webhooks -> the webhook's "Secret"
    razorpay_webhook_secret: str = ""

    # Phase 7 — observability & logging. Both optional: an empty
    # sentry_dsn means error tracking is simply off (see
    # core/observability.py), and log_level just controls verbosity.
    sentry_dsn: str = ""
    log_level: str = "INFO"

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    @property
    def cors_origins(self) -> list[str]:
        """`frontend_origin` split on commas and trimmed — what
        CORSMiddleware actually wants (a list), while the env var itself
        stays a plain human-editable string."""
        return [origin.strip() for origin in self.frontend_origin.split(",") if origin.strip()]


# Imported everywhere else as: from app.core.config import settings
settings = Settings()
