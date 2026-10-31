import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, field_validator, model_validator

from app.core.support_rules import (
    KINDS,
    ORDER_ACTIONS,
    ORDER_KINDS,
    REASONS,
    REVIEW_OUTCOMES,
    RULINGS,
    SHOP_ACTIONS,
    SHOP_RESPONSE_TYPES,
    clean_photos,
)


def _text(v: str | None, *, required: bool, limit: int, what: str) -> str | None:
    v = (v or "").strip()
    if not v:
        if required:
            raise ValueError(f"{what} is required")
        return None
    return v[:limit]


class _Photos(BaseModel):
    photos: list[str] = []

    @field_validator("photos")
    @classmethod
    def _photos_ok(cls, v: list[str]) -> list[str]:
        return clean_photos(v)


class CaseCreate(_Photos):
    kind: str
    reason: str
    description: str
    order_id: uuid.UUID | None = None
    shop_id: uuid.UUID | None = None

    @field_validator("kind")
    @classmethod
    def _kind(cls, v: str) -> str:
        if v not in KINDS:
            raise ValueError(f"kind must be one of {KINDS}")
        return v

    @field_validator("description")
    @classmethod
    def _desc(cls, v: str) -> str:
        return _text(v, required=True, limit=2000, what="Please describe what happened")  # type: ignore[return-value]

    @model_validator(mode="after")
    def _shape(self):
        if self.reason not in REASONS[self.kind]:
            raise ValueError("Choose one of the listed reasons")
        if self.kind in ORDER_KINDS and self.order_id is None:
            raise ValueError("order_id is required for an order or payment problem")
        if self.kind == "shop_report" and self.shop_id is None:
            raise ValueError("shop_id is required to report a shop")
        return self


class InfoReply(_Photos):
    message: str

    @field_validator("message")
    @classmethod
    def _m(cls, v: str) -> str:
        return _text(v, required=True, limit=1000, what="A message")  # type: ignore[return-value]


class EscalateRequest(BaseModel):
    note: str | None = None

    @field_validator("note")
    @classmethod
    def _n(cls, v: str | None) -> str | None:
        return _text(v, required=False, limit=1000, what="Note")


class ShopReply(_Photos):
    response_type: str
    message: str

    @field_validator("response_type")
    @classmethod
    def _t(cls, v: str) -> str:
        if v not in SHOP_RESPONSE_TYPES:
            raise ValueError(f"response_type must be one of {SHOP_RESPONSE_TYPES}")
        return v

    @field_validator("message")
    @classmethod
    def _m(cls, v: str) -> str:
        return _text(v, required=True, limit=2000, what="A message")  # type: ignore[return-value]


class ActionDone(BaseModel):
    note: str | None = None

    @field_validator("note")
    @classmethod
    def _n(cls, v: str | None) -> str | None:
        return _text(v, required=False, limit=1000, what="Note")


class RuleRequest(BaseModel):
    ruling: str
    note: str
    order_action: str | None = None
    action_days: int = 3
    action_note: str | None = None
    internal_note: str | None = None

    @field_validator("ruling")
    @classmethod
    def _r(cls, v: str) -> str:
        if v not in RULINGS:
            raise ValueError(f"ruling must be one of {RULINGS}")
        return v

    @field_validator("note")
    @classmethod
    def _n(cls, v: str) -> str:
        return _text(v, required=True, limit=1000, what="A note for both sides")  # type: ignore[return-value]

    @field_validator("order_action")
    @classmethod
    def _a(cls, v: str | None) -> str | None:
        if v is not None and v not in ORDER_ACTIONS:
            raise ValueError(f"order_action must be one of {ORDER_ACTIONS}")
        return v

    @field_validator("action_days")
    @classmethod
    def _d(cls, v: int) -> int:
        if not 1 <= v <= 30:
            raise ValueError("action_days must be between 1 and 30")
        return v

    @field_validator("action_note", "internal_note")
    @classmethod
    def _o(cls, v: str | None) -> str | None:
        return _text(v, required=False, limit=1000, what="Note")

    @model_validator(mode="after")
    def _only_when_customer_wins(self):
        if self.order_action and self.ruling != "customer":
            raise ValueError("A refund/resend can only be ordered when ruling in favour of the customer")
        return self


class ReviewRequest(BaseModel):
    outcome: str
    internal_note: str | None = None

    @field_validator("outcome")
    @classmethod
    def _o(cls, v: str) -> str:
        if v not in REVIEW_OUTCOMES:
            raise ValueError(f"outcome must be one of {REVIEW_OUTCOMES}")
        return v

    @field_validator("internal_note")
    @classmethod
    def _n(cls, v: str | None) -> str | None:
        return _text(v, required=False, limit=1000, what="Note")


class ShopActionRequest(BaseModel):
    action: str
    note: str | None = None

    @field_validator("action")
    @classmethod
    def _a(cls, v: str) -> str:
        if v not in SHOP_ACTIONS:
            raise ValueError(f"action must be one of {SHOP_ACTIONS}")
        return v

    @field_validator("note")
    @classmethod
    def _n(cls, v: str | None) -> str | None:
        return _text(v, required=False, limit=1000, what="Note")

    @model_validator(mode="after")
    def _warn_needs_text(self):
        if self.action in ("warn", "hide_shop") and not self.note:
            raise ValueError("Add a note — the shop will see it")
        return self


class FlagRequest(BaseModel):
    flagged: bool
    note: str | None = None

    @field_validator("note")
    @classmethod
    def _n(cls, v: str | None) -> str | None:
        return _text(v, required=False, limit=300, what="Note")


class InternalNote(BaseModel):
    internal_note: str | None = None

    @field_validator("internal_note")
    @classmethod
    def _n(cls, v: str | None) -> str | None:
        return _text(v, required=False, limit=2000, what="Note")


# ---------------------------------------------------------------- outputs

class CaseEventOut(BaseModel):
    id: uuid.UUID
    kind: str
    actor: str
    note: str | None
    created_at: datetime


class CustomerStats(BaseModel):
    cases_total: int
    ruled_against_60d: int
    suggest_flag: bool
    flagged_at: datetime | None
    flag_note: str | None


class SupportCaseOut(BaseModel):
    """One shape for all three audiences. Fields a given audience must not see
    are left None/empty by core/support_view.py — never filtered by the client."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    kind: str
    kind_label: str
    status: str
    reason: str
    reason_label: str
    description: str
    photos: list[str]
    resolution: str | None

    order_id: uuid.UUID | None = None
    order_ref: str | None = None
    order_status: str | None = None
    order_total: str | None = None
    shop_id: uuid.UUID | None = None
    shop_name: str | None = None
    customer_name: str | None = None
    customer_id: uuid.UUID | None = None  # admin only

    shop_due_at: datetime | None = None
    overdue: bool = False
    auto_close_at: datetime | None = None

    info_request_text: str | None = None
    info_requested_at: datetime | None = None
    info_reply_text: str | None = None
    info_reply_photos: list[str] = []
    info_replied_at: datetime | None = None

    shop_response_type: str | None = None
    shop_response_label: str | None = None
    shop_response_text: str | None = None
    shop_response_photos: list[str] = []
    shop_responded_at: datetime | None = None

    escalated_at: datetime | None = None
    escalation_note: str | None = None

    ruling: str | None = None
    ruling_label: str | None = None
    ruling_note: str | None = None
    ruled_at: datetime | None = None
    order_action: str | None = None
    order_action_note: str | None = None
    order_action_deadline: datetime | None = None
    order_action_done_at: datetime | None = None
    action_overdue: bool = False

    # shop_report / general: all the reporter sees of the outcome.
    review_outcome: str | None = None
    # Admin only:
    internal_note: str | None = None
    customer_stats: CustomerStats | None = None

    created_at: datetime
    updated_at: datetime
    resolved_at: datetime | None = None

    # What the viewer can do right now (the server decides, the UI follows).
    can_accept: bool = False
    can_escalate: bool = False
    can_reply_info: bool = False
    can_reply: bool = False
    can_request_info: bool = False
    can_mark_action_done: bool = False
    can_rule: bool = False
    can_review: bool = False

    events: list[CaseEventOut] = []


class SupportOptions(BaseModel):
    kinds: list[dict]
    reasons: dict[str, list[dict]]
    report_window_days: int
    shop_reply_hours: int
    auto_close_days: int
    max_photos: int


class AdminSummary(BaseModel):
    escalated: int
    overdue: int
    direct_reports: int
    action_overdue: int
    open_total: int
