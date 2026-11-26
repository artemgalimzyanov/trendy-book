"""One daily run: trends -> sentence -> story.json + notes -> (chapter close).

Every intermediate file is written to output/<date>/ (a CI artifact, not committed).
The "already done?" check reads the committed docs/story.json, because output/ does
not survive between CI runs, and it happens before any network call.
"""

import json
import logging
from pathlib import Path

from book import dates, story
from book.chapter import apply_close, close_chapter
from book.config import DATA_DIR, output_dir_for
from book.trends import DEFAULT_COUNT, get_trends
from book.writer import build_context, system_prompt, write_day

log = logging.getLogger(__name__)

BOOK_COMPLETE = "book complete"
NOT_STARTED = "not started"


def _write_json(path: Path, data) -> None:
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n")


def _needs_close(book: dict, number: int) -> bool:
    return bool(story.chapter_days(book, number)) and story.get_chapter(book, number) is None


def _close(book: dict, number: int, final: bool, dry_run: bool, data_dir: Path, providers) -> dict:
    notes = story.load_notes(number, data_dir)
    result = close_chapter(book, number, notes, final=final, providers=providers, dry_run=dry_run)
    if not dry_run:
        apply_close(book, number, result)
    log.info("Chapter %d closed: %s", number, result["title"])
    return result


def run(
    run_date: str | None = None,
    trends: list[str] | None = None,
    dry_run: bool = False,
    force: bool = False,
    n: int = DEFAULT_COUNT,
    providers=None,
    story_path: Path | None = None,
    data_dir: Path | None = None,
) -> dict:
    """Write the sentence for run_date (default: today, UTC).

    dry_run=True makes no paid call (headline-fallback trends, template sentence and
    chapter close) and leaves docs/ and data/ untouched: only output/<date>/ is written.
    """
    run_date = run_date or dates.today_utc()
    story_path = story_path or story.STORY_PATH
    data_dir = data_dir or DATA_DIR
    result = {"date": run_date, "dry_run": dry_run}

    # 1. nothing to write before the rehearsal month or after the last day
    if dates.as_date(run_date) < dates.REHEARSAL_START:
        log.info("%s is before the rehearsal (%s): %s", run_date, dates.REHEARSAL_START, NOT_STARTED)
        return {**result, "status": NOT_STARTED}
    number = dates.chapter_for(run_date)
    if number is None:
        log.info("%s is after %s: %s", run_date, dates.END_DATE, BOOK_COMPLETE)
        return {**result, "status": BOOK_COMPLETE}
    result["chapter"] = number
    closes_chapter = dates.is_chapter_end(run_date)
    final = dates.is_book_end(run_date)

    # 2. skip if done, before any network call; finish a close that failed last time
    book = story.load(story_path)
    if story.has_day(book, run_date) and not force:
        if closes_chapter and _needs_close(book, number):
            out = output_dir_for(run_date)
            log.info("%s is written but chapter %d is still open; closing it", run_date, number)
            result["chapter_close"] = _close(book, number, final, dry_run, data_dir, providers)
            if not dry_run:
                story.save(book, story_path)
            result["status"] = "closed"
            _write_json(out / "result.json", result)
            return result
        log.info("%s is already written; use --force to redo it", run_date)
        return {**result, "status": "skipped", "day": story.get_day(book, run_date)}

    out = output_dir_for(run_date)

    # 2b. a previous chapter left open (its last run failed) is closed before moving on
    previous = number - 1
    if previous >= 1 and _needs_close(book, previous):
        log.info("Chapter %d was never closed; closing it first", previous)
        result["previous_chapter_close"] = _close(book, previous, False, dry_run, data_dir, providers)
        if not dry_run:
            story.save(book, story_path)

    # 3. trends
    trends = trends or get_trends(n=n, dry_run=dry_run)
    _write_json(out / "trends.json", trends)
    log.info("Trends: %s", trends)

    # 4. the sentence
    notes = story.load_notes(number, data_dir)
    context = build_context(book, notes, run_date, trends)
    (out / "context.txt").write_text(
        f"=== SYSTEM\n{system_prompt(run_date, len(trends))}\n\n=== USER\n{context}\n"
    )
    try:
        written = write_day(book, notes, run_date, trends, providers=providers, dry_run=dry_run)
    except Exception as exc:
        _write_json(out / "reply.json", {"error": str(exc)})
        raise
    _write_json(out / "reply.json", written)

    # 5. store the day and the notes
    day = {
        "date": run_date,
        "chapter": number,
        "trends": trends,
        "keywords": written["keywords"],
        "sentence": written["sentence"],
        "writer": written["writer"],
    }
    result["day"] = day
    if not dry_run:
        story.add_day(book, day)
        story.save_notes(number, written["notes"], data_dir)
        story.save(book, story_path)
        log.info("Day %s saved (%s)", run_date, written["writer"])

    # 6. last day of the month: close the chapter (and name the book on the last day)
    if closes_chapter:
        if dry_run:
            book = story.add_day(json.loads(json.dumps(book)), day)  # a copy, so the close sees today
        result["chapter_close"] = _close(book, number, final, dry_run, data_dir, providers)
        if not dry_run:
            story.save(book, story_path)

    # 7. artifacts
    result["status"] = "written"
    _write_json(out / "result.json", result)
    log.info("Done: %s", out / "result.json")
    return result
