import asyncio
from logging.config import fileConfig

from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import create_async_engine

from alembic import context

# Import our settings + all models so Alembic knows both:
# 1. which database to connect to (settings.database_url)
# 2. what tables SHOULD exist (Base.metadata, via app/models/__init__.py)
from app.core.config import settings
from app.models import Base

config = context.config

# Feed our real DATABASE_URL (from .env) into Alembic instead of whatever
# placeholder is in alembic.ini — this is what lets `alembic upgrade head`
# work against your actual Supabase database without editing alembic.ini.
config.set_main_option("sqlalchemy.url", settings.database_url)

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# This is what makes `alembic revision --autogenerate` work: Alembic diffs
# this metadata (what the models say should exist) against the live
# database (what actually exists) and writes the migration for you.
target_metadata = Base.metadata


def run_migrations_offline() -> None:
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection: Connection) -> None:
    context.configure(connection=connection, target_metadata=target_metadata)
    with context.begin_transaction():
        context.run_migrations()


async def run_migrations_online() -> None:
    # We use create_async_engine here because our app uses the async
    # (asyncpg) driver everywhere else — Alembic needs its own connection,
    # run synchronously under the hood via run_sync().
    connectable = create_async_engine(settings.database_url, poolclass=pool.NullPool)

    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)

    await connectable.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    asyncio.run(run_migrations_online())
