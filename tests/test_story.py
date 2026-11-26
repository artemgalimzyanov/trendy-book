import json

from book import story


def _day(date, chapter=1, sentence=None, keywords=("Ebola", "spy")):
    return {
        "date": date,
        "chapter": chapter,
        "trends": ["Kenya Ebola case", "German spy arrest"],
        "keywords": list(keywords),
        "sentence": sentence or f"On {date} the spy read about Ebola.",
        "writer": "gemini:test",
        "extra_field_not_stored": True,
    }


def test_load_missing_file_is_an_empty_story(tmp_path):
    book = story.load(tmp_path / "nope.json")
    assert book == story.empty_story()
    assert book["title"] == "Working Title"
    assert (book["start"], book["end"]) == ("2027-01-01", "2027-12-31")


def test_save_then_load_round_trips(tmp_path):
    path = tmp_path / "docs" / "story.json"
    book = story.add_day(story.empty_story(), _day("2027-01-01"))
    story.save(book, path)
    assert story.load(path) == book
    assert json.loads(path.read_text())["days"][0]["date"] == "2027-01-01"


def test_add_day_keeps_only_day_fields(tmp_path):
    book = story.add_day(story.empty_story(), _day("2027-01-01"))
    assert set(book["days"][0]) == set(story.DAY_FIELDS)


def test_add_day_sorts_by_date_and_replaces_same_day():
    book = story.empty_story()
    story.add_day(book, _day("2027-01-03"))
    story.add_day(book, _day("2027-01-01"))
    story.add_day(book, _day("2027-01-03", sentence="Redone."))

    assert [d["date"] for d in book["days"]] == ["2027-01-01", "2027-01-03"]
    assert story.get_day(book, "2027-01-03")["sentence"] == "Redone."
    assert story.has_day(book, "2027-01-01") and not story.has_day(book, "2027-01-02")


def test_chapter_days_filters_by_chapter():
    book = story.empty_story()
    for d, ch in [("2026-12-30", 0), ("2027-01-01", 1), ("2027-02-01", 2), ("2027-01-02", 1)]:
        story.add_day(book, _day(d, chapter=ch))
    assert [d["date"] for d in story.chapter_days(book, 1)] == ["2027-01-01", "2027-01-02"]
    assert [d["date"] for d in story.chapter_days(book, 0)] == ["2026-12-30"]


def test_set_chapter_inserts_or_replaces_sorted():
    book = story.empty_story()
    story.set_chapter(book, 2, "2027-02", "Second", "s2")
    story.set_chapter(book, 1, "2027-01", "First", "s1")
    story.set_chapter(book, 2, "2027-02", "Second Again", "s2b")
    assert [(c["number"], c["title"]) for c in book["chapters"]] == [(1, "First"), (2, "Second Again")]
    assert set(book["chapters"][0]) == set(story.CHAPTER_FIELDS)


def test_notes_use_a_separate_file_for_the_rehearsal(tmp_path):
    assert story.load_notes(1, tmp_path) == ""
    story.save_notes(0, "rehearsal notes", tmp_path)
    story.save_notes(3, "  real notes\n\n", tmp_path)

    assert (tmp_path / "notes-rehearsal.md").read_text() == "rehearsal notes\n"
    assert (tmp_path / "notes.md").read_text() == "real notes\n"
    assert story.load_notes(0, tmp_path) == "rehearsal notes"
    assert story.load_notes(12, tmp_path) == "real notes"


def test_render_text_brackets_keywords_and_shows_gaps():
    book = story.empty_story()
    story.add_day(book, _day("2027-01-01", sentence="Two spies met where Ebola's name was never said."))
    story.add_day(book, _day("2027-01-03"))
    story.set_chapter(book, 1, "2027-01", "Cold Open", "A summary.")
    story.add_day(book, _day("2026-12-31", chapter=0))

    text = story.render_text(book)
    assert "CHAPTER 01 // Cold Open\nA summary." in text
    assert "2027-01-01  Two [spies] met where [Ebola's] name was never said." in text
    assert "2027-01-02  ▒ signal lost ▒" in text
    assert "2026-12-31" not in text  # the rehearsal only shows when asked for

    rehearsal = story.render_text(book, chapter=0)
    assert "REHEARSAL // IN PROGRESS" in rehearsal and "2026-12-31  On 2026-12-31 the [spy]" in rehearsal
