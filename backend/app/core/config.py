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

    # Which frontend origin is allowed to call this API (CORS)
    frontend_origin: str = "http://localhost:3000"

    # Stripe test-mode keys (Stripe Dashboard -> Developers -> API keys)
    stripe_secret_key: str = ""
    # From `stripe listen` (local dev) or the webhook endpoint's settings (production)
    stripe_webhook_secret: str = ""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


# Imported everywhere else as: from app.core.config import settings
settings = Settings()
