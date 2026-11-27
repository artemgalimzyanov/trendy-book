import json

import pytest

from book import story, writer
from book.words import check
from tests.fakes import fake_provider, no_call_provider

TRENDS = [
    "Kenya first Ebola case",
    "German spy chief arrest",
    "Black Sea ship attack",
    "French student protests",
    "Bolsonaro Brazil election surge",
]
KEYWORDS = ["Ebola", "spy", "Black Sea", "student", "Bolsonaro"]
SENTENCE = (
    "Mara, a nursing student who had stopped reading about Ebola, watched a stranger spy on "
    "the ferry from the Black Sea café, wondering whether Bolsonaro's grin on the television "
    "meant anything to anyone here."
)
GOOD = {"keywords": KEYWORDS, "sentence": SENTENCE, "notes": "Mara, 24, nursing student, restless."}


def _day(date, chapter, sentence):
    return {"date": date, "chapter": chapter, "trends": TRENDS, "keywords": KEYWORDS,
            "sentence": sentence, "writer": "test"}


# --- write_day ---------------------------------------------------------------------


def test_passes_first_try():
    gemini = fake_provider("gemini", GOOD)
    result = writer.write_day(story.empty_story(), "old notes", "2027-01-05", TRENDS, [gemini, no_call_provider()])

    assert result["sentence"] == SENTENCE
    assert result["keywords"] == KEYWORDS
    assert result["notes"] == GOOD["notes"]
    assert result["writer"] == "gemini:m"
    assert len(result["attempts"]) == 1
    call = gemini.client.calls[0]
    assert "Today's arc: Build the situation." in call["messages"][0]["content"]
    assert "TODAY'S TOPICS (2027-01-05)\n1. Kenya first Ebola case" in call["messages"][1]["content"]


def test_retries_after_a_missing_keyword_with_the_problems_listed():
    missing = {**GOOD, "sentence": SENTENCE.replace("Ebola", "the outbreak")}
    gemini = fake_provider("gemini", missing, GOOD)

    result = writer.write_day(story.empty_story(), "", "2027-01-05", TRENDS, [gemini, no_call_provider()])

    assert result["writer"] == "gemini:m"
    assert len(result["attempts"]) == 2
    retry = gemini.client.calls[1]["messages"]
    assert retry[2]["role"] == "assistant" and "the outbreak" in retry[2]["content"]
    assert retry[3]["content"].startswith("Fix: the sentence must contain the keyword(s): 'Ebola'")


def test_openai_without_credit_falls_back_to_gemini():
    openai = fake_provider("openai", RuntimeError("429 insufficient_quota"), model="gpt-5.4-mini")
    gemini = fake_provider("gemini", GOOD, model="gemini-3.8-flash")

    result = writer.write_day(story.empty_story(), "", "2027-01-05", TRENDS, [openai, gemini])

    assert result["writer"] == "gemini:gemini-3.8-flash"
    assert len(openai.client.calls) == 1  # an API error is not retried on the same provider
    assert result["attempts"][0]["error"] == "RuntimeError: 429 insufficient_quota"


def test_bad_json_is_retried_once():
    gemini = fake_provider("gemini", "sorry, here you go", json.dumps(GOOD))
    result = writer.write_day(story.empty_story(), "", "2027-01-05", TRENDS, [gemini])
    assert result["writer"] == "gemini:m"
    assert gemini.client.calls[1]["messages"][-1]["content"].startswith("Fix: respond with one JSON object")


def test_everything_fails_raises():
    bad = {**GOOD, "sentence": "Too short."}
    gemini = fake_provider("gemini", bad, bad)
    openai = fake_provider("openai", bad, bad)
    with pytest.raises(writer.WriterError) as err:
        writer.write_day(story.empty_story(), "", "2027-01-05", TRENDS, [gemini, openai])
    assert len(gemini.client.calls) == 2 and len(openai.client.calls) == 2
    assert "2027-01-05" in str(err.value)


def test_missing_notes_keep_the_old_notes():
    gemini = fake_provider("gemini", {**GOOD, "notes": ""})
    assert writer.write_day(story.empty_story(), "old", "2027-01-05", TRENDS, [gemini])["notes"] == "old"


def test_dry_run_makes_no_calls_and_passes_the_check(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    result = writer.write_day(story.empty_story(), "notes", "2027-01-05", TRENDS, [no_call_provider()], dry_run=True)
    assert check(TRENDS, result["keywords"], result["sentence"]) == []
    assert result["writer"] == writer.DRY_RUN_WRITER
    assert result["notes"] == "notes"


@pytest.mark.parametrize("n", [1, 2, 3, 5, 7])
def test_dry_run_passes_the_check_for_any_number_of_trends(n):
    trends = [f"Topic number {i} about Placename{i}" for i in range(n)]
    result = writer.dry_run_day("", trends)
    assert check(trends, result["keywords"], result["sentence"]) == []


def test_dry_run_passes_the_check_on_real_world_headlines():
    trends = [
        "US announces new tariffs on host of countries including China",
        "Markets digest bank earnings after recent turmoil",
        "Swiss tourist killed and British and Americans injured by elephants in Cameroon",
        "Island Paradise of Mauritius Has Sun, Beaches and Too Many Dogs",
        "Nigeria detains 5 Mexicans, confiscates over $220 million of meth",
    ]
    result = writer.dry_run_day("", trends)
    assert check(trends, result["keywords"], result["sentence"]) == []


# --- build_context -------------------------------------------------------------------


def _book():
    book = story.empty_story()
    story.add_day(book, _day("2026-12-31", 0, "REHEARSAL SENTENCE."))
    for i in range(1, 32):
        story.add_day(book, _day(f"2027-01-{i:02d}", 1, f"January sentence {i}."))
    story.add_day(book, _day("2027-02-01", 2, "February sentence 1."))
    story.add_day(book, _day("2027-02-02", 2, "February sentence 2."))
    story.set_chapter(book, 0, "2026-12", "Rehearsal", "REHEARSAL SUMMARY")
    story.set_chapter(book, 1, "2027-01", "Cold Open", "January summary.")
    return book


def test_context_mid_chapter_has_summaries_and_only_earlier_days():
    text = writer.build_context(_book(), "my notes", "2027-02-02", TRENDS)

    assert text.startswith("NOTES\nmy notes\n\nEARLIER CHAPTERS\nChapter 1: Cold Open\nJanuary summary.")
    assert "THIS CHAPTER (2, day 2 of 28)\n2027-02-01: February sentence 1." in text
    assert "February sentence 2." not in text  # the day being written (e.g. --force) is not shown
    assert "January sentence" not in text  # earlier chapters only as summaries
    assert "LAST SENTENCES" not in text
    assert "REHEARSAL" not in text
    assert text.endswith("TODAY'S TOPICS (2027-02-02)\n1. Kenya first Ebola case\n2. German spy chief arrest\n"
                         "3. Black Sea ship attack\n4. French student protests\n5. Bolsonaro Brazil election surge")


def test_context_on_the_first_shows_the_end_of_the_previous_chapter():
    text = writer.build_context(_book(), "", "2027-02-01", TRENDS)
    assert ("LAST SENTENCES OF PREVIOUS CHAPTER\n2027-01-29: January sentence 29.\n"
            "2027-01-30: January sentence 30.\n2027-01-31: January sentence 31.") in text
    assert "THIS CHAPTER (2, day 1 of 28)\n(no sentences yet)" in text


def test_context_on_new_years_day_never_sees_the_rehearsal():
    text = writer.build_context(_book(), "", "2027-01-01", TRENDS)
    assert "REHEARSAL" not in text
    assert "EARLIER CHAPTERS\n(none)" in text
    assert "LAST SENTENCES" not in text
    assert "NOTES\n(empty" in text


def test_context_for_the_rehearsal_shows_its_own_days():
    text = writer.build_context(_book(), "", "2026-12-31", TRENDS)
    assert "EARLIER CHAPTERS" not in text
    assert "THIS CHAPTER (0, day 31 of 31)\n(no sentences yet)" in text


def test_context_after_the_end_is_an_error():
    with pytest.raises(ValueError):
        writer.build_context(_book(), "", "2028-01-01", TRENDS)


def test_system_prompt_carries_the_arc_hint():
    assert "Today's arc: This is the final sentence of the novel." in writer.system_prompt("2027-12-31")
    assert '{"keywords": [5 keywords, in topic order]' in writer.system_prompt("2027-03-03")
