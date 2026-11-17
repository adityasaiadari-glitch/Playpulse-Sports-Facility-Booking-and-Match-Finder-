"""
Dates, times and slots  (Unit III: Working with Dates and Times)
Also shows a GENERATOR (Unit II: Generators and Iterators).
"""
from datetime import date, datetime, timedelta

from .exceptions import ValidationError
from .validators import DATE_RE
import re

MAX_DAYS_AHEAD = 14          # bookings allowed up to 2 weeks ahead
CANCEL_HOURS_BEFORE = 2      # free cancellation until 2 hours before start


def today():
    return date.today()


def parse_date(text):
    """'2026-11-20' -> date(2026, 11, 20). Raises ValidationError if invalid."""
    text = (text or "").strip()
    if not re.fullmatch(DATE_RE, text):
        raise ValidationError("Date: use the format YYYY-MM-DD")
    try:
        return datetime.strptime(text, "%Y-%m-%d").date()     # strptime: string -> date
    except ValueError:                                        # e.g. 2026-02-31
        raise ValidationError("Date: that day does not exist")


def check_bookable_date(d):
    """A date must be today or within the next MAX_DAYS_AHEAD days."""
    if d < today():
        raise ValidationError("You cannot book a date in the past")
    if d > today() + timedelta(days=MAX_DAYS_AHEAD):
        raise ValidationError(f"Bookings open only {MAX_DAYS_AHEAD} days in advance")
    return d


def hour_slots(opens, closes):
    """
    GENERATOR: yields one hour at a time instead of building a whole list.
    hour_slots(6, 10) -> 6, 7, 8, 9
    """
    hour = opens
    while hour < closes:
        yield hour
        hour += 1


def start_datetime(d, hour):
    """Combine a date and an hour into a datetime."""
    return datetime.combine(d, datetime.min.time()) + timedelta(hours=hour)


def is_past(d, hour):
    return start_datetime(d, hour) <= datetime.now()


def is_weekend(d):
    return d.weekday() >= 5          # Monday=0 ... Saturday=5, Sunday=6


def hour_label(hour):
    """13 -> '01:00 PM'   (strftime: datetime -> string)"""
    return datetime(2000, 1, 1, hour % 24).strftime("%I:%M %p")


def range_label(hour, duration=1):
    return f"{hour_label(hour)} – {hour_label(hour + duration)}"


def pretty_date(d):
    """date(2026,11,20) -> 'Fri, 20 Nov 2026'"""
    return d.strftime("%a, %d %b %Y")


def next_days(n=7):
    """List of the next n dates as (iso_string, label) pairs for date pickers."""
    out = []
    for i in range(n):
        d = today() + timedelta(days=i)
        label = "Today" if i == 0 else ("Tomorrow" if i == 1 else d.strftime("%a %d"))
        out.append((d.isoformat(), label))
    return out


def can_cancel(d, hour):
    """True if there are still at least CANCEL_HOURS_BEFORE hours to start."""
    return start_datetime(d, hour) - datetime.now() >= timedelta(hours=CANCEL_HOURS_BEFORE)
