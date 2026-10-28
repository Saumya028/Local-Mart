"""
Opening hours, vacation closures and "is this shop taking orders right now?".

Storage format (Shop.opening_hours, JSON):

    {"mon": [{"open": "09:00", "close": "21:00"}],
     "tue": [{"open": "09:00", "close": "13:00"}, {"open": "16:00", "close": "21:00"}],
     "sat": [{"open": "18:00", "close": "02:00"}],     # overnight: closes 2 AM Sunday
     "sun": []}                                         # closed all day

Rules
  * times are 24h "HH:MM" in the shop's own timezone (Shop.timezone);
  * "24:00" as a closing time means "until midnight";
  * a close time at or before the open time means the range runs past
    midnight into the next day;
  * opening_hours = NULL means the owner has not set hours: the shop is
    treated as always open (so shops that existed before this feature work
    exactly as they did);
  * temporarily_closed (+ optional closed_until) overrides everything.

All datetimes handed in or out are timezone-aware; internally comparisons
are done in UTC.
"""
import re
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

DAYS = ("mon", "tue", "wed", "thu", "fri", "sat", "sun")
MAX_INTERVALS_PER_DAY = 3
DEFAULT_TZ = "Asia/Kolkata"
_HM = re.compile(r"^(\d{2}):(\d{2})$")
_LOOKAHEAD = timedelta(days=8)

Window = tuple[datetime, datetime]


# ---------------------------------------------------------------- validation

def _minutes(value: str, *, allow_24: bool) -> int:
    m = _HM.match(value.strip()) if isinstance(value, str) else None
    if not m:
        raise ValueError(f"Time {value!r} must look like 09:30")
    h, mi = int(m.group(1)), int(m.group(2))
    if h == 24 and mi == 0 and allow_24:
        return 24 * 60
    if h > 23 or mi > 59:
        raise ValueError(f"Time {value!r} isn't a valid 24-hour time")
    return h * 60 + mi


def _fmt(minutes: int) -> str:
    return f"{minutes // 60:02d}:{minutes % 60:02d}"


def validate_timezone(name: str) -> str:
    try:
        ZoneInfo(name)
    except (ZoneInfoNotFoundError, ValueError, OSError):
        raise ValueError(f"Unknown timezone {name!r} (use a name like Asia/Kolkata)") from None
    return name


def normalize_opening_hours(value: dict | None) -> dict | None:
    """Validate and canonicalise. Returns a dict with all 7 day keys, or None.
    Raises ValueError with a message meant for the shop owner."""
    if value is None:
        return None
    if not isinstance(value, dict):
        raise ValueError("Opening hours must be a day-by-day schedule")
    unknown = set(value) - set(DAYS)
    if unknown:
        raise ValueError(f"Unknown day(s): {', '.join(sorted(map(str, unknown)))}")

    out: dict[str, list[dict]] = {}
    total = 0
    for day in DAYS:
        raw = value.get(day) or []
        if not isinstance(raw, list):
            raise ValueError(f"Hours for {day} must be a list of open/close ranges")
        if len(raw) > MAX_INTERVALS_PER_DAY:
            raise ValueError(f"At most {MAX_INTERVALS_PER_DAY} time ranges per day ({day})")
        parsed: list[tuple[int, int]] = []
        for item in raw:
            if not isinstance(item, dict) or "open" not in item or "close" not in item:
                raise ValueError(f"Each range for {day} needs an open and a close time")
            o = _minutes(item["open"], allow_24=False)
            c = _minutes(item["close"], allow_24=True)
            if o == c:
                raise ValueError(f"On {day}, opening and closing times can't be the same")
            parsed.append((o, c))
        parsed.sort()
        for i, (o, c) in enumerate(parsed):
            overnight = c <= o
            if overnight and i != len(parsed) - 1:
                raise ValueError(f"On {day}, only the last range can run past midnight")
            end_same_day = 24 * 60 if overnight else c
            if i + 1 < len(parsed) and parsed[i + 1][0] < end_same_day:
                raise ValueError(f"On {day}, time ranges overlap")
        out[day] = [{"open": _fmt(o), "close": _fmt(c)} for o, c in parsed]
        total += len(parsed)
    if total == 0:
        raise ValueError(
            "Add opening hours for at least one day, or clear the schedule. "
            "(To close for a while, use “Temporarily closed” instead.)"
        )
    return out


# ------------------------------------------------------------------ windows

def zone_of(shop) -> ZoneInfo:
    try:
        return ZoneInfo(getattr(shop, "timezone", None) or DEFAULT_TZ)
    except (ZoneInfoNotFoundError, ValueError, OSError):
        return ZoneInfo(DEFAULT_TZ)


def _at(d: date, minutes: int, zone: ZoneInfo) -> datetime:
    """Local wall-clock `minutes` after midnight of date `d`, as aware UTC."""
    base = datetime.combine(d, time(0, 0), tzinfo=zone)
    return (base + timedelta(minutes=minutes)).astimezone(timezone.utc)


def _merge(windows: list[Window]) -> list[Window]:
    windows.sort()
    merged: list[Window] = []
    for start, end in windows:
        if merged and start <= merged[-1][1]:
            if end > merged[-1][1]:
                merged[-1] = (merged[-1][0], end)
        else:
            merged.append((start, end))
    return merged


def is_closed_temporarily(shop, now: datetime) -> bool:
    if not getattr(shop, "temporarily_closed", False):
        return False
    until = getattr(shop, "closed_until", None)
    return until is None or until > now


def open_windows(shop, start: datetime, end: datetime, now: datetime | None = None) -> list[Window]:
    """The stretches inside [start, end] during which the shop is open
    (UTC-aware, sorted, merged, vacation excluded)."""
    now = now or datetime.now(timezone.utc)
    start = start.astimezone(timezone.utc)
    end = end.astimezone(timezone.utc)
    if is_closed_temporarily(shop, now):
        until = getattr(shop, "closed_until", None)
        if until is None:
            return []
        start = max(start, until.astimezone(timezone.utc))
    if start >= end:
        return []

    hours = getattr(shop, "opening_hours", None)
    if not hours:
        return [(start, end)]

    zone = zone_of(shop)
    raw: list[Window] = []
    first = start.astimezone(zone).date() - timedelta(days=1)  # yesterday's overnight range may reach into today
    last = end.astimezone(zone).date()
    d = first
    while d <= last:
        for rng in hours.get(DAYS[d.weekday()]) or []:
            o = _minutes(rng["open"], allow_24=False)
            c = _minutes(rng["close"], allow_24=True)
            w_start = _at(d, o, zone)
            w_end = _at(d, c, zone) if c > o else _at(d + timedelta(days=1), c, zone)
            raw.append((w_start, w_end))
        d += timedelta(days=1)

    clipped = [(max(a, start), min(b, end)) for a, b in _merge(raw) if b > start and a < end]
    return [w for w in clipped if w[1] > w[0]]


# ------------------------------------------------------------------- status

@dataclass(frozen=True)
class OpenStatus:
    is_open: bool
    # "open" | "closed_hours" | "temporarily_closed"
    state: str
    opens_at: datetime | None   # when it next opens (None if open now, or unknown)
    closes_at: datetime | None  # when the current open spell ends (None = no schedule)
    message: str | None = None  # owner's note while temporarily closed

    def as_dict(self) -> dict:
        return {
            "is_open": self.is_open,
            "state": self.state,
            "opens_at": self.opens_at.isoformat() if self.opens_at else None,
            "closes_at": self.closes_at.isoformat() if self.closes_at else None,
            "message": self.message,
        }


def open_status(shop, now: datetime | None = None) -> OpenStatus:
    now = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    closed_now = is_closed_temporarily(shop, now)
    message = getattr(shop, "closed_message", None) if closed_now else None

    if not closed_now and not getattr(shop, "opening_hours", None):
        return OpenStatus(True, "open", None, None)

    windows = open_windows(shop, now, now + _LOOKAHEAD, now)
    for w_start, w_end in windows:
        if w_start <= now < w_end:
            # (a temporary closure that already ended is no longer "closed_now")
            return OpenStatus(True, "open", None, w_end if getattr(shop, "opening_hours", None) else None)
    upcoming = next((w for w in windows if w[0] > now), None)
    state = "temporarily_closed" if closed_now else "closed_hours"
    return OpenStatus(False, state, upcoming[0] if upcoming else None, None, message)


# --------------------------------------------------------------- formatting

def local_time_text(dt: datetime, zone: ZoneInfo, now: datetime | None = None) -> str:
    """"6:30 PM", "tomorrow 9:00 AM", or "Mon 9:00 AM" — in the shop's timezone."""
    now = now or datetime.now(timezone.utc)
    local = dt.astimezone(zone)
    today = now.astimezone(zone).date()
    clock = local.strftime("%I:%M %p").lstrip("0")
    if local.date() == today:
        return clock
    if local.date() == today + timedelta(days=1):
        return f"tomorrow {clock}"
    return f"{local.strftime('%a')} {clock}"


def describe_eta(
    eta_at: datetime | None,
    slot_start: datetime | None,
    slot_end: datetime | None,
    zone: ZoneInfo,
    now: datetime | None = None,
) -> str | None:
    """Human wording for an order's expected time, e.g. "between 6:00 PM and
    7:00 PM", "by 6:30 PM", "by tomorrow 10:00 AM"."""
    if slot_start and slot_end:
        return f"between {local_time_text(slot_start, zone, now)} and {local_time_text(slot_end, zone, now).replace('tomorrow ', '')}"
    if eta_at:
        return f"by {local_time_text(eta_at, zone, now)}"
    return None
