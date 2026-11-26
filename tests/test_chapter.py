import pytest

from book import chapter, story
from tests.fakes import fake_provider, no_call_provider

SUMMARY = " ".join(["Mara kept the ferry ticket and the secret of the stranger."] * 7)  # 77 words
GOOD = {"title": "The Ferry in Winter", "summary": SUMMARY}


def _book():
    book = story.empty_story()
    for date, ch in [("2026-12-31", 0), ("2027-01-01", 1), ("2027-01-31", 1), ("2027-02-01", 2)]:
        story.add_day(book, {"date": date, "chapter": ch, "trends": [], "keywords": [],
                             "sentence": f"Sentence of {date}.", "writer": "t"})
    story.set_chapter(book, 0, "2026-12", "Rehearsal", "REHEARSAL SUMMARY")
    return book


def test_close_returns_title_and_summary():
    gemini = fake_provider("gemini", {**GOOD, "title": '"The Ferry in Winter."'})
    result = chapter.close_chapter(_book(), 1, "notes", providers=[gemini, no_call_provider()])

    assert result["title"] == "The Ferry in Winter"
    assert result["summary"] == SUMMARY
    assert result["writer"] == "gemini:m"
    assert "book_title" not in result
    user = gemini.client.calls[0]["messages"][1]["content"]
    assert "THIS CHAPTER (1, 2027-01)\n2027-01-01: Sentence of 2027-01-01.\n2027-01-31: Sentence of 2027-01-31." in user
    assert "2027-02-01" not in user and "REHEARSAL" not in user


def test_final_close_also_names_the_book():
    gemini = fake_provider("gemini", {**GOOD, "book_title": "Signal Lost"})
    result = chapter.close_chapter(_book(), 12, "", final=True, providers=[gemini])
    assert result["book_title"] == "Signal Lost"
    assert '"book_title"' in gemini.client.calls[0]["messages"][0]["content"]


def test_short_summary_is_retried_with_the_problem():
    gemini = fake_provider("gemini", {**GOOD, "summary": "Too short."}, GOOD)
    result = chapter.close_chapter(_book(), 1, "", providers=[gemini])
    assert result["summary"] == SUMMARY
    assert gemini.client.calls[1]["messages"][-1]["content"].startswith("Fix: the summary has 2 words")


def test_final_close_needs_a_book_title():
    gemini = fake_provider("gemini", GOOD, GOOD)
    openai = fake_provider("openai", {**GOOD, "book_title": "Signal Lost"})
    result = chapter.close_chapter(_book(), 12, "", final=True, providers=[gemini, openai])
    assert result["writer"] == "openai:m"


def test_gemini_error_falls_back_and_total_failure_raises():
    gemini = fake_provider("gemini", RuntimeError("503"))
    openai = fake_provider("openai", GOOD)
    assert chapter.close_chapter(_book(), 1, "", providers=[gemini, openai])["writer"] == "openai:m"

    with pytest.raises(chapter.ChapterError):
        chapter.close_chapter(_book(), 1, "", providers=[fake_provider("gemini", RuntimeError("x"))])


def test_dry_run_makes_no_calls_and_passes_its_own_check():
    result = chapter.close_chapter(_book(), 1, "", final=True, providers=[no_call_provider()], dry_run=True)
    assert chapter.check_reply(result["title"], result["summary"], result["book_title"]) == []
    assert result["title"] == "Untitled January"


def test_rehearsal_context_has_no_earlier_chapters():
    text = chapter.build_context(_book(), 0, "")
    assert "EARLIER CHAPTERS" not in text
    assert "THIS CHAPTER (0, 2026-12)\n2026-12-31: Sentence of 2026-12-31." in text


def test_apply_close_stores_chapter_and_book_title():
    book = chapter.apply_close(_book(), 12, {"title": "End", "summary": "s", "book_title": "Signal Lost"})
    assert story.get_chapter(book, 12) == {"number": 12, "month": "2027-12", "title": "End", "summary": "s"}
    assert book["title"] == "Signal Lost"

    book = chapter.apply_close(_book(), 1, {"title": "Start", "summary": "s"})
    assert book["title"] == story.WORKING_TITLE
    assert story.get_chapter(book, 1)["month"] == "2027-01"
