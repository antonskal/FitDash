"""Time parsing helpers for the many timestamp formats Garmin emits."""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from typing import Any

GARMIN_GMT_FORMATS = (
    "%Y-%m-%dT%H:%M:%S.%f",
    "%Y-%m-%dT%H:%M:%S",
    "%Y-%m-%d %H:%M:%S.%f",
    "%Y-%m-%d %H:%M:%S",
)


def now_utc() -> datetime:
    return datetime.now(UTC)


def now_iso() -> str:
    return now_utc().isoformat(timespec="seconds")


def iso_date(d: date | datetime) -> str:
    return d.strftime("%Y-%m-%d")


def parse_date(s: str) -> date:
    return datetime.strptime(s[:10], "%Y-%m-%d").date()


def iter_dates(start: date, end: date, reverse: bool = False):
    """Yield every date in [start, end] inclusive."""
    days = (end - start).days
    rng = range(days, -1, -1) if reverse else range(days + 1)
    for i in rng:
        yield start + timedelta(days=i)


def to_epoch_ms(dt: datetime) -> int:
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=UTC)
    return int(dt.timestamp() * 1000)


def parse_gmt_ms(value: Any) -> int | None:
    """Parse a Garmin GMT timestamp (string in several formats, or epoch ms) → epoch ms."""
    if value is None:
        return None
    if isinstance(value, (int, float)):
        # Garmin epoch values are milliseconds; anything < 1e11 is seconds.
        return int(value if value > 1e11 else value * 1000)
    if isinstance(value, str):
        s = value.strip()
        if not s:
            return None
        if s.endswith("Z"):
            s = s[:-1]
        for fmt in GARMIN_GMT_FORMATS:
            try:
                return to_epoch_ms(datetime.strptime(s, fmt).replace(tzinfo=UTC))
            except ValueError:
                continue
        try:
            return to_epoch_ms(datetime.fromisoformat(s))
        except ValueError:
            return None
    return None


def parse_naive(value: str | None) -> datetime | None:
    """Parse a Garmin timestamp string without attaching a timezone."""
    if not value:
        return None
    s = value.strip().rstrip("Z")
    for fmt in GARMIN_GMT_FORMATS:
        try:
            return datetime.strptime(s, fmt)
        except ValueError:
            continue
    return None


def local_offset_ms(gmt: str | None, local: str | None) -> int | None:
    """Offset (local - GMT) in ms derived from a pair of Garmin timestamps."""
    g, l = parse_naive(gmt), parse_naive(local)
    if g is None or l is None:
        return None
    return int((l - g).total_seconds() * 1000)


def ms_to_dt(ms: int) -> datetime:
    return datetime.fromtimestamp(ms / 1000, tz=UTC)
