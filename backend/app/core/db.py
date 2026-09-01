from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import settings

# `engine` manages the actual pool of connections to Postgres.
# echo=False keeps SQL statements out of the logs in normal operation;
# flip to True temporarily if you need to debug a query.
#
# pool_pre_ping=True makes SQLAlchemy issue a cheap "is this connection
# still alive" check before handing a pooled connection to a request.
# Without this, a connection that Supabase's pooler (or your OS) silently
# closed after sitting idle looks perfectly fine to SQLAlchemy until you
# actually try to use it — which is exactly the
# `asyncpg.exceptions._base.InterfaceError: connection is closed` seen in
# the logs. pre_ping catches that dead connection and transparently
# reconnects instead of surfacing a 500 on the next request that happens
# to grab it.
#
# pool_recycle=1800 proactively recycles any connection older than 30
# minutes, so we never even get close to whatever idle-timeout Supabase's
# pooler enforces on its end.
engine = create_async_engine(
    settings.database_url,
    echo=False,
    future=True,
    pool_pre_ping=True,
    pool_recycle=1800,
)

# A factory that hands out new AsyncSession objects.
# expire_on_commit=False means objects stay usable after a commit,
# which avoids a common FastAPI gotcha where accessing an object's
# fields after commit() triggers a surprise extra query.
AsyncSessionLocal = async_sessionmaker(engine, expire_on_commit=False)


async def get_db():
    """
    FastAPI dependency: yields a database session for the duration of one
    request, and guarantees it's closed afterwards even if the request
    raises an exception.

    Usage in a route:
        async def some_route(db: AsyncSession = Depends(get_db)):
            ...
    """
    async with AsyncSessionLocal() as session:
        yield session
