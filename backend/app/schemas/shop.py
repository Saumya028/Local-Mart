import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, field_validator

# Kept in sync by hand with admin.py's VALID_DOCS_STATUSES:
# "pending"   — no documents on file yet, or an admin has explicitly
#                requested new/additional ones (see routers/admin.py's
#                request_shop_docs) and is waiting on the owner.
# "submitted" — the owner has uploaded document(s) and it's now the
#                admin's turn to review them.
# "verified"  — an admin has reviewed and accepted the documents.
VALID_DOCS_STATUSES = ("pending", "submitted", "verified")


class ShopDocument(BaseModel):
    name: str  # human label, e.g. "GST Certificate"
    doc_type: str  # e.g. "gst_certificate", "id_proof", "address_proof", "other"
    url: str  # Supabase Storage URL — see frontend/lib/documentUpload.ts


class ShopCreate(BaseModel):
    name: str
    category: str
    # Selling isn't self-service (see routers/shops.py's create_shop
    # docstring), and neither is skipping verification: an application
    # with zero documents attached isn't reviewable, so the platform
    # would have nothing to approve against. This is what actually closes
    # the gap a real test run found — a shop used to become fully
    # operable the instant this endpoint returned, with nothing uploaded
    # and nothing blocking it.
    documents: list[ShopDocument]

    @field_validator("documents")
    @classmethod
    def at_least_one_document(cls, v: list[ShopDocument]) -> list[ShopDocument]:
        if len(v) < 1:
            raise ValueError(
                "At least one verification document (e.g. a business "
                "registration certificate or owner ID proof) is required to apply."
            )
        return v


class ShopUpdate(BaseModel):
    name: str | None = None
    category: str | None = None
    is_active: bool | None = None
    # Lets an owner resubmit documents after a rejection or a
    # "Request Docs" admin action, via the SAME endpoint
    # (PUT /dashboard/shops/{id}) rather than a separate one — see that
    # route's handling: setting this also flips docs_status back to
    # "submitted" and clears any prior rejection_reason.
    documents: list[ShopDocument] | None = None


class ShopOut(BaseModel):
    """
    The PUBLIC shape — returned by GET /shops and GET /shops/{id}, which
    anyone (including a logged-out visitor) can call. Deliberately does
    NOT include approval_status, docs_status, documents, or
    rejection_reason: `documents` holds URLs to a seller's ID proof and
    business registration, which must never be reachable from a public,
    unauthenticated endpoint. See DashboardShopOut below for the
    owner/admin-facing shape that does include them.
    """

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    category: str
    rating: float
    is_active: bool
    created_at: datetime


class DashboardShopOut(ShopOut):
    """
    The OWNER-facing shape — GET/PUT /dashboard/shops only, always
    behind require_role("shop_owner", "admin") + an ownership check.
    Adds exactly the fields the Shop Dashboard needs to render "your
    application is pending/rejected/approved" and let the owner act on
    it (see ShopUpdate.documents above).
    """

    approval_status: str
    docs_status: str
    documents: list[ShopDocument]
    rejection_reason: str | None
