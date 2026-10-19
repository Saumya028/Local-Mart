import uuid
from datetime import datetime

from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    SmallInteger,
    String,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class RecommendationRun(Base):
    """
    One execution of the nightly model build (scripts/build_recommendations.py).
    The API only ever reads similarity/popularity rows belonging to the
    single run with is_active = true, so a build in progress (or a failed or
    rejected one) can never be seen by customers, and rolling back is just
    re-activating the previous "ready" run.

    status: building -> ready (built, and active if promoted) | rejected
            (failed the quality gate, rows deleted) | failed (crashed).
    `stats` holds counts and the offline evaluation (hit_rate, ndcg,
    popularity baseline, coverage) that the promote gate and the admin
    tab read.
    """

    __tablename__ = "recommendation_runs"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    status: Mapped[str] = mapped_column(String, default="building", server_default="building", index=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    stats: Mapped[dict] = mapped_column(JSONB, default=dict, server_default="{}")
    error: Mapped[str | None] = mapped_column(String, nullable=True)

    __table_args__ = (
        # At most ONE active run, enforced by the database itself.
        Index("uq_recommendation_one_active", "is_active", unique=True, postgresql_where=text("is_active")),
    )


class ProductSimilarity(Base):
    """
    "Customers who bought product_id also bought similar_product_id".
    kind = "also_bought"     — across a customer's whole history (product page, home)
           "bought_together" — within the same order/basket (cart page)
    Top-N neighbours per product only (settings.reco_neighbors_per_product).
    """

    __tablename__ = "product_similarity"

    run_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("recommendation_runs.id", ondelete="CASCADE"), primary_key=True
    )
    kind: Mapped[str] = mapped_column(String, primary_key=True)
    product_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("products.id", ondelete="CASCADE"), primary_key=True
    )
    similar_product_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("products.id", ondelete="CASCADE"), primary_key=True
    )
    score: Mapped[float] = mapped_column(Float)
    co_buyers: Mapped[int] = mapped_column(Integer)

    __table_args__ = (
        # Serves "who are similar_product_id's neighbours" lookups used when
        # a product is deleted/cascaded and by admin diagnostics.
        Index("ix_product_similarity_similar", "similar_product_id"),
    )


class ProductPopularity(Base):
    """Recency-weighted distinct-buyer score per product, per run — the
    "trending" signal and the popularity baseline the model must beat."""

    __tablename__ = "product_popularity"

    run_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("recommendation_runs.id", ondelete="CASCADE"), primary_key=True
    )
    product_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("products.id", ondelete="CASCADE"), primary_key=True
    )
    score: Mapped[float] = mapped_column(Float)
    buyers_30d: Mapped[int] = mapped_column(Integer, default=0, server_default="0")


class RecommendationEvent(Base):
    """
    Raw shelf telemetry: an impression (a product was shown), click or
    add_to_cart from a recommendation shelf. One row per product. Used ONLY
    to measure click-through and attributed orders (routers/
    admin_recommendations.py) — never fed back into the model. Deleted after
    settings.reco_event_retention_days, and when the user's account goes.
    """

    __tablename__ = "recommendation_events"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)
    user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("profiles.id", ondelete="CASCADE"), nullable=True
    )
    surface: Mapped[str] = mapped_column(String)  # product | cart | home | buy_again
    event: Mapped[str] = mapped_column(String)  # impression | click | add_to_cart
    product_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("products.id", ondelete="CASCADE")
    )
    position: Mapped[int | None] = mapped_column(SmallInteger, nullable=True)
    run_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    variant: Mapped[str] = mapped_column(String, default="model", server_default="model")

    __table_args__ = (
        Index("ix_reco_events_surface_event_created", "surface", "event", "created_at"),
        Index("ix_reco_events_user_product_created", "user_id", "product_id", "created_at"),
    )
