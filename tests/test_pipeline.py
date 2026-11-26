import json

import pytest

from book import pipeline, story
from tests.fakes import no_call_provider

TRENDS = [
    "Kenya first Ebola case",
    "German spy chief arrest",
    "Black Sea ship attack",
    "French student protests",
    "Bolsonaro Brazil election surge",
]


@pytest.fixture
def env(tmp_path, monkeypatch):
    """Temp output/, docs/story.json and data/; every model step recorded in `calls`."""
    out, docs, data = tmp_path / "output", tmp_path / "docs", tmp_path / "data"
    monkeypatch.setattr(pipeline, "output_dir_for", lambda d: _mk(out / d))
    calls = []

    def fake_trends(**kw):
        calls.append(("trends", kw["dry_run"]))
        return TRENDS

    def fake_write(book, notes, run_date, trends, **kw):
        calls.append(("write", run_date))
        return {"keywords": ["Ebola"] * 5, "sentence": f"Sentence for {run_date}.",
                "notes": f"notes after {run_date}", "writer": "gemini:test", "attempts": []}

    def fake_close(book, number, notes, final=False, **kw):
        calls.append(("close", number, final))
        result = {"title": f"Title {number}", "summary": "Summary.", "writer": "gemini:test", "attempts": []}
        return {**result, "book_title": "The Book"} if final else result

    monkeypatch.setattr(pipeline, "get_trends", fake_trends)
    monkeypatch.setattr(pipeline, "write_day", fake_write)
    monkeypatch.setattr(pipeline, "close_chapter", fake_close)

    class Env:
        pass

    e = Env()
    e.out, e.docs, e.data, e.calls = out, docs, data, calls
    e.story_path = docs / "story.json"
    e.run = lambda d, **kw: pipeline.run(d, story_path=e.story_path, data_dir=data, **kw)
    e.load = lambda: story.load(e.story_path)
    return e


def _mk(path):
    path.mkdir(parents=True, exist_ok=True)
    return path


def test_run_calls_steps_in_order_and_saves_everything(env):
    result = env.run("2027-01-05")

    assert env.calls == [("trends", False), ("write", "2027-01-05")]
    assert result["status"] == "written"
    book = env.load()
    assert story.get_day(book, "2027-01-05") == {
        "date": "2027-01-05", "chapter": 1, "trends": TRENDS, "keywords": ["Ebola"] * 5,
        "sentence": "Sentence for 2027-01-05.", "writer": "gemini:test",
    }
    assert story.load_notes(1, env.data) == "notes after 2027-01-05"
    folder = env.out / "2027-01-05"
    for name in ["trends.json", "context.txt", "reply.json", "result.json"]:
        assert (folder / name).exists(), name
    assert "TODAY'S TOPICS (2027-01-05)" in (folder / "context.txt").read_text()


def test_given_trends_skip_the_fetch(env):
    env.run("2027-01-05", trends=["a", "b"])
    assert env.calls == [("write", "2027-01-05")]


def test_existing_day_is_skipped_before_any_network_call(env, monkeypatch):
    env.run("2027-01-05")
    env.calls.clear()
    monkeypatch.setattr(pipeline, "output_dir_for", lambda d: pytest.fail("no output before the skip"))

    result = env.run("2027-01-05")
    assert result["status"] == "skipped"
    assert result["day"]["sentence"] == "Sentence for 2027-01-05."
    assert env.calls == []


def test_force_redoes_the_day(env):
    env.run("2027-01-05")
    env.run("2027-01-05", force=True)
    assert env.calls.count(("write", "2027-01-05")) == 2
    assert len(env.load()["days"]) == 1


def test_dry_run_leaves_docs_and_data_untouched(env, monkeypatch):
    monkeypatch.undo()  # the real writer and chapter close, in dry-run mode
    monkeypatch.setattr(pipeline, "output_dir_for", lambda d: _mk(env.out / d))
    monkeypatch.setattr(pipeline, "get_trends", lambda **kw: TRENDS if kw["dry_run"] else pytest.fail("paid"))

    result = pipeline.run("2027-01-31", dry_run=True, providers=[no_call_provider()],
                          story_path=env.story_path, data_dir=env.data)

    assert result["status"] == "written"
    assert result["day"]["writer"] == "dry-run"
    assert result["chapter_close"]["title"] == "Untitled January"
    assert not env.docs.exists() and not env.data.exists()
    saved = json.loads((env.out / "2027-01-31" / "result.json").read_text())
    assert saved["day"]["sentence"] == result["day"]["sentence"]


def test_chapter_closes_only_on_its_last_day(env):
    env.run("2027-02-27")
    assert ("close", 2, False) not in env.calls
    env.run("2027-02-28")
    assert env.calls[-1] == ("close", 2, False)
    assert story.get_chapter(env.load(), 2)["title"] == "Title 2"
    assert env.load()["title"] == story.WORKING_TITLE


def test_last_day_closes_the_book(env):
    result = env.run("2027-12-31")
    assert env.calls[-1] == ("close", 12, True)
    assert result["chapter_close"]["book_title"] == "The Book"
    assert env.load()["title"] == "The Book"


def test_rehearsal_closes_on_new_years_eve_without_naming_the_book(env):
    env.run("2026-12-31")
    assert env.calls[-1] == ("close", 0, False)
    assert story.load_notes(0, env.data) == "notes after 2026-12-31"
    assert not (env.data / "notes.md").exists()


def test_nothing_happens_before_the_rehearsal_month(env):
    # the cron starts as soon as the repo is pushed; November must not open or close chapter 0
    result = env.run("2026-11-30")
    assert result["status"] == pipeline.NOT_STARTED
    assert env.calls == []
    assert not env.out.exists() and not env.docs.exists()
    assert env.run("2026-12-01")["status"] == "written"


def test_nothing_happens_after_the_end(env):
    result = env.run("2028-01-01")
    assert result["status"] == pipeline.BOOK_COMPLETE
    assert env.calls == []
    assert not env.out.exists() and not env.docs.exists()


def test_a_failed_close_is_finished_by_the_next_slot(env, monkeypatch):
    real_close = pipeline.close_chapter
    monkeypatch.setattr(pipeline, "close_chapter", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("503")))
    with pytest.raises(RuntimeError):
        env.run("2027-03-31")
    assert story.has_day(env.load(), "2027-03-31") and story.get_chapter(env.load(), 3) is None

    monkeypatch.setattr(pipeline, "close_chapter", real_close)
    env.calls.clear()
    result = env.run("2027-03-31")
    assert result["status"] == "closed"
    assert env.calls == [("close", 3, False)]  # no new trends, no new sentence
    assert story.get_chapter(env.load(), 3)["title"] == "Title 3"


def test_an_unclosed_previous_chapter_is_closed_first(env):
    env.run("2027-03-30")  # the 31st never ran
    env.calls.clear()
    env.run("2027-04-01")
    assert env.calls == [("close", 3, False), ("trends", False), ("write", "2027-04-01")]
    assert story.get_chapter(env.load(), 3) is not None


def test_writer_failure_is_saved_and_raised(env, monkeypatch):
    monkeypatch.setattr(pipeline, "write_day", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("all failed")))
    with pytest.raises(RuntimeError):
        env.run("2027-01-05")
    assert "all failed" in (env.out / "2027-01-05" / "reply.json").read_text()
    assert not env.docs.exists()
