from datetime import date

import pytest

from book import dates


def test_rehearsal_day_is_chapter_zero():
    d = "2026-12-15"
    assert dates.chapter_for(d) == 0
    assert dates.chapter_month(d) == "2026-12"
    assert dates.day_of_chapter(d) == 15
    assert dates.days_in_chapter(d) == 31
    assert not dates.is_chapter_end(d)
    assert dates.arc_hint(d) == "Complicate it."


def test_rehearsal_closes_on_new_years_eve():
    assert dates.chapter_for("2026-12-31") == 0
    assert dates.is_chapter_end("2026-12-31")
    assert not dates.is_book_end("2026-12-31")


def test_first_day_of_the_book():
    d = "2027-01-01"
    assert dates.chapter_for(d) == 1
    assert dates.book_day(d) == 1
    assert "first sentence of the novel" in dates.arc_hint(d)


def test_end_of_february_closes_chapter_two():
    d = "2027-02-28"
    assert dates.chapter_for(d) == 2
    assert dates.days_in_chapter(d) == 28
    assert dates.is_chapter_end(d)
    assert not dates.is_book_end(d)
    assert "closes the chapter" in dates.arc_hint(d)


def test_last_day_of_the_book():
    d = "2027-12-31"
    assert dates.chapter_for(d) == 12
    assert dates.is_chapter_end(d)
    assert dates.is_book_end(d)
    assert dates.book_day(d) == dates.book_length() == 365
    assert "final sentence of the novel" in dates.arc_hint(d)


def test_after_the_end_there_is_no_chapter():
    assert dates.chapter_for("2028-01-01") is None
    with pytest.raises(ValueError):
        dates.arc_hint("2028-01-01")


@pytest.mark.parametrize(
    "day, hint",
    [
        ("2027-03-01", "Begin a new arc."),
        ("2027-03-02", "Build the situation."),
        ("2027-03-10", "Build the situation."),
        ("2027-03-11", "Complicate it."),
        ("2027-03-20", "Complicate it."),
        ("2027-03-21", "Move toward a turning point."),
        ("2027-03-28", "Move toward a turning point."),
        ("2027-03-29", "Resolve the arc."),
        ("2027-03-30", "Resolve the arc."),
        ("2027-02-25", "Move toward a turning point."),
        ("2027-02-26", "Resolve the arc."),
    ],
)
def test_arc_hints_follow_the_month(day, hint):
    assert dates.arc_hint(day) == hint


def test_accepts_date_objects_and_today_is_iso():
    assert dates.chapter_for(date(2027, 7, 4)) == 7
    assert date.fromisoformat(dates.today_utc())
