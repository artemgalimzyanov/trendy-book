from book import dates, sample, story
from book.words import check


def test_sample_has_75_days_two_closed_chapters_one_in_progress_and_one_gap():
    book = sample.build()
    dated = [d["date"] for d in book["days"]]
    assert dated[0] == "2027-01-01" and dated[-1] == "2027-03-16"
    assert dates.book_day(dated[-1]) == sample.SAMPLE_DAYS == 75
    assert len(dated) == 74 and sample.GAP_DATE not in dated
    assert [c["number"] for c in book["chapters"]] == [1, 2]
    assert story.chapter_days(book, 3) and story.get_chapter(book, 3) is None


def test_every_sample_day_passes_the_check():
    for day in sample.build()["days"]:
        assert check(day["trends"], day["keywords"], day["sentence"]) == [], day["date"]
        assert len(set(day["trends"])) == 5


def test_sample_summaries_fit_the_chapter_rules():
    from book.chapter import check_reply

    for c in sample.build()["chapters"]:
        assert check_reply(c["title"], c["summary"], None) == []


def test_write_saves_a_loadable_story(tmp_path):
    path = sample.write(tmp_path / "story.sample.json")
    assert story.load(path) == sample.build()
