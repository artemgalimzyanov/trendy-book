"""Close a chapter: a title and a summary, plus the book's title after the last chapter.

The summary is the chapter's only memory for the rest of the year, because the writer
sees earlier chapters only as title + summary. Same provider fallback as the writer.
"""

import json
import logging
from datetime import date

from book import dates, story
from book.llm import Provider, chat_json, providers as default_providers

log = logging.getLogger(__name__)

ATTEMPTS_PER_PROVIDER = 2
# The prompt asks for 2-5 and 60-100 words; the check is looser, like words.check().
TITLE_WORDS = (1, 7)
SUMMARY_WORDS = (45, 130)
BOOK_TITLE_WORDS = (1, 8)
DRY_RUN_WRITER = "dry-run"

CHAPTER_SYSTEM_PROMPT = """\
You are the author of a literary novel written one sentence a day for one year, set in the \
real present-day world and following a few ordinary, fictional people. A month has ended, and \
with it a chapter.
1. Give the chapter a title of 2-5 words, in the voice of the novel. No quotation marks.
2. Write a summary of 60-100 words in the past tense: who the characters are, what happened to \
them, and which threads are still open. It will be the only memory of this chapter when the \
rest of the book is written, so keep names, places and threads exact. Mention world news only \
as the characters lived it.{final}
Respond with JSON only: {{"title": "...", "summary": "..."{final_key}}}"""

FINAL_RULE = (
    "\n3. This was the last chapter, and the novel is finished. Propose the novel's final title "
    "(1-6 words), drawn from the whole year."
)


class ChapterError(RuntimeError):
    """Every provider and every attempt failed to close the chapter."""


def system_prompt(final: bool = False) -> str:
    return CHAPTER_SYSTEM_PROMPT.format(
        final=FINAL_RULE if final else "",
        final_key=', "book_title": "..."' if final else "",
    )


def chapter_month(book: dict, number: int) -> str:
    """'YYYY-MM' of a chapter: from its days, else from its number."""
    days = story.chapter_days(book, number)
    if days:
        return days[0]["date"][:7]
    if number == dates.REHEARSAL:
        return date(dates.START_DATE.year - 1, 12, 1).strftime("%Y-%m")
    return date(dates.START_DATE.year, number, 1).strftime("%Y-%m")


def build_context(book: dict, number: int, notes: str) -> str:
    """The user message: notes, earlier chapters (book proper only) and every sentence of this one."""
    sections = [("NOTES", notes.strip() or "(none)")]
    if number != dates.REHEARSAL:
        earlier = [c for c in book["chapters"] if dates.REHEARSAL < c["number"] < number]
        text = "\n\n".join(f"Chapter {c['number']}: {c['title']}\n{c['summary']}" for c in earlier)
        sections.append(("EARLIER CHAPTERS", text or "(none)"))
    days = story.chapter_days(book, number)
    sections.append(
        (f"THIS CHAPTER ({number}, {chapter_month(book, number)})",
         "\n".join(f"{d['date']}: {d['sentence']}" for d in days) or "(no sentences)")
    )
    return "\n\n".join(f"{title}\n{body}" for title, body in sections)


def _clean_title(value) -> str:
    return " ".join(value.split()).strip(" \"“”'‘’.") if isinstance(value, str) else ""


def _clean_text(value) -> str:
    return " ".join(value.split()) if isinstance(value, str) else ""


def _count(text: str) -> int:
    return len(text.split())


def check_reply(title: str, summary: str, book_title: str | None) -> list[str]:
    problems = []
    if not TITLE_WORDS[0] <= _count(title) <= TITLE_WORDS[1]:
        problems.append(f"the title has {_count(title)} words; use 2 to 5")
    if not SUMMARY_WORDS[0] <= _count(summary) <= SUMMARY_WORDS[1]:
        problems.append(f"the summary has {_count(summary)} words; write 60 to 100")
    if book_title is not None and not BOOK_TITLE_WORDS[0] <= _count(book_title) <= BOOK_TITLE_WORDS[1]:
        problems.append(f"the book_title has {_count(book_title)} words; use 1 to 6")
    return problems


def dry_run_close(book: dict, number: int, final: bool = False) -> dict:
    days = story.chapter_days(book, number)
    month = date.fromisoformat(chapter_month(book, number) + "-01").strftime("%B")
    first = days[0]["sentence"] if days else "Nothing was written."
    summary = (
        f"A dry-run summary of the {month} chapter, written without a model call so the "
        f"pipeline can be tested end to end. The chapter has {len(days)} sentences. It opened "
        f"like this: {first} The real summary will name the characters, what happened to them "
        "during the month and which threads stay open for the chapters that follow."
    )
    result = {"title": f"Untitled {month}", "summary": summary, "writer": DRY_RUN_WRITER, "attempts": []}
    if final:
        result["book_title"] = "Untitled Novel"
    return result


def close_chapter(
    book: dict,
    number: int,
    notes: str,
    final: bool = False,
    providers: list[Provider] | None = None,
    dry_run: bool = False,
) -> dict:
    """Return {"title", "summary", "writer", "attempts"} (+ "book_title" when final)."""
    if dry_run:
        return dry_run_close(book, number, final)

    system = system_prompt(final)
    user = build_context(book, number, notes)
    attempts: list[dict] = []

    for provider in providers if providers is not None else default_providers():
        followup: list[dict] = []
        for attempt in range(1, ATTEMPTS_PER_PROVIDER + 1):
            record = {"writer": provider.label, "attempt": attempt}
            attempts.append(record)
            try:
                reply = chat_json(provider, system, user, followup)
            except ValueError as exc:
                record["problems"] = [str(exc)]
                followup = [{"role": "user", "content": "Fix: respond with one JSON object only."}]
                continue
            except Exception as exc:
                record["error"] = f"{type(exc).__name__}: {exc}"
                log.warning("%s failed (%s); trying the next provider", provider.label, record["error"])
                break

            title, summary = _clean_title(reply.get("title")), _clean_text(reply.get("summary"))
            book_title = _clean_title(reply.get("book_title")) if final else None
            problems = check_reply(title, summary, book_title)
            if not problems:
                result = {"title": title, "summary": summary, "writer": provider.label, "attempts": attempts}
                if final:
                    result["book_title"] = book_title
                return result
            record["problems"] = problems
            log.warning("%s attempt %d: %s", provider.label, attempt, "; ".join(problems))
            followup = [
                {"role": "assistant", "content": json.dumps(reply, ensure_ascii=False)},
                {"role": "user", "content": "Fix: " + "; ".join(problems) + ". Respond with the full JSON again."},
            ]

    raise ChapterError(f"No provider closed chapter {number}: {json.dumps(attempts, ensure_ascii=False)}")


def apply_close(book: dict, number: int, result: dict) -> dict:
    """Store a close result in the story: the chapter entry, and the book title when final."""
    story.set_chapter(book, number, chapter_month(book, number), result["title"], result["summary"])
    if result.get("book_title"):
        book["title"] = result["book_title"]
    return book
