from pydantic import BaseModel


class PlatformStatsOut(BaseModel):
    """
    Backs the homepage's hero badge ("2,400+ local shops") and bottom CTA
    ("Join over N customers") — both were fabricated numbers in the
    mockup. Rather than hardcode those, this is a tiny, genuinely public
    (no auth) stats endpoint so the homepage shows the platform's real
    current counts instead.
    """

    total_shops: int
    total_customers: int
