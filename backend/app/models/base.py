from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    """
    Every model inherits from this. Alembic points at `Base.metadata` to
    know what tables should exist — so any new model file must be imported
    somewhere (see app/models/__init__.py) or Alembic won't see it.
    """
    pass
