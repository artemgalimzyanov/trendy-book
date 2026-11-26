"""Calendar rules of the book: chapters, day numbers, arc hints. Pure, UTC only.

A chapter is a calendar month of 2027 (chapter 1 = January ... 12 = December).
December 2026 is chapter 0, the rehearsal, which follows the same month rules but is
never shown to the writer or on the page. Runs before REHEARSAL_START write nothing.
"""

import calendar
from datetime import date, datetime, timezone

REHEARSAL_START = date(2026, 12, 1)
START_DATE = date(2027, 1, 1)
END_DATE = date(2027, 12, 31)
REHEARSAL = 0

DateLike = date | str


def as_date(d: DateLike) -> date:
    return d if isinstance(d, date) else date.fromisoformat(d)


def today_utc() -> str:
    """Today's date in UTC as an ISO string; CI runners and laptops must agree."""
    return datetime.now(timezone.utc).date().isoformat()


def chapter_for(d: DateLike) -> int | None:
    """0 before the start (rehearsal), 1-12 during the year, None after the end."""
    d = as_date(d)
    if d < START_DATE:
        return REHEARSAL
    if d > END_DATE:
        return None
    return d.month


def chapter_month(d: DateLike) -> str:
    """The chapter's calendar month as 'YYYY-MM'."""
    return as_date(d).strftime("%Y-%m")


def day_of_chapter(d: DateLike) -> int:
    return as_date(d).day


def days_in_chapter(d: DateLike) -> int:
    d = as_date(d)
    return calendar.monthrange(d.year, d.month)[1]


def is_chapter_end(d: DateLike) -> bool:
    return day_of_chapter(d) == days_in_chapter(d)


def is_book_end(d: DateLike) -> bool:
    return as_date(d) == END_DATE


def book_day(d: DateLike) -> int:
    """1 on the first day of the book, 365 on the last; <= 0 during the rehearsal."""
    return (as_date(d) - START_DATE).days + 1


def book_length() -> int:
    return (END_DATE - START_DATE).days + 1


def arc_hint(d: DateLike) -> str:
    """Where the day sits in its chapter's arc, as an instruction for the writer."""
    d = as_date(d)
    if chapter_for(d) is None:
        raise ValueError(f"{d} is after the end of the book")
    if d == START_DATE:
        return "This is the first sentence of the novel. Open the story and begin the first arc."
    if is_book_end(d):
        return "This is the final sentence of the novel. Resolve the arc and end the book."

    day, total = day_of_chapter(d), days_in_chapter(d)
    if day == 1:
        return "Begin a new arc."
    if day == total:
        return "Resolve the arc. This sentence closes the chapter."
    if day > total - 3:
        return "Resolve the arc."
    if day <= 10:
        return "Build the situation."
    if day <= 20:
        return "Complicate it."
    return "Move toward a turning point."
