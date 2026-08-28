from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import settings

# `engine` manages the actual pool of connections to Postgres.
# echo=False keeps SQL statements out of the logs in normal operation;
# flip to True temporarily if you need to debug a query.
engine = create_async_engine(settings.database_url, echo=False, future=True)

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
