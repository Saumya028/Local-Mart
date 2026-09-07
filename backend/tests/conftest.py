import os

# app.core.config.Settings() requires database_url/redis_url with no
# default (correctly — production should never silently fall back to
# something). For these tests, which never actually open either
# connection (see the README section on what this suite does and
# doesn't cover), dummy-but-well-formed values are enough to let the app
# import and construct without a real Postgres/Redis reachable in CI.
os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://user:pass@localhost:5432/test")
os.environ.setdefault("REDIS_URL", "redis://localhost:6379")
os.environ.setdefault("SUPABASE_JWT_SECRET", "test-secret")
os.environ.setdefault("SUPABASE_URL", "https://test.supabase.co")
os.environ.setdefault("FRONTEND_ORIGIN", "http://localhost:3000")
