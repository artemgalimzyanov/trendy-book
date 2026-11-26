"""Write the day's sentence: build the context, ask the model, check, retry, fall back.

Each provider gets up to ATTEMPTS_PER_PROVIDER tries. A reply that fails words.check()
is retried with "Fix: <problems>"; an API error moves straight on to the next provider.
"""

import json
import logging

from book import dates, story
from book.llm import Provider, chat_json, providers as default_providers
from book.words import check, fallback_keywords

log = logging.getLogger(__name__)

ATTEMPTS_PER_PROVIDER = 2
PREVIOUS_CHAPTER_TAIL = 3  # last sentences of the previous chapter shown at a chapter's start
NOTES_MAX_WORDS = 200
DRY_RUN_WRITER = "dry-run"

SYSTEM_PROMPT = """\
You are the author of a literary novel written one sentence a day for one year, set in the \
real present-day world and following a few ordinary, fictional people. The day's world news \
reaches them the way news reaches anyone: a radio, a phone screen, a conversation, a passing thought.
1. From each of today's {n} topics pick ONE keyword that appears in the topic text exactly \
(one word, or a name of up to two words). Prefer the most specific word.
2. Write the next sentence of the novel. It must contain all {n} keywords. A keyword may be used \
in any sense, so a "strike" can be the strike of a match. The sentence must never read like a \
list of headlines.
3. Write exactly one sentence of 20-50 words, in the third person and past tense, in the same \
voice as the story so far. Continue from the last sentence. Keep names, places and open threads \
consistent with your notes, and add new characters rarely.
4. Real public figures never appear as characters, only as news. Never quote headlines. Treat \
deaths, wars and disasters with restraint, never as jokes.
5. Today's arc: {arc_hint}
6. Update your notes ({notes_max} words or less): characters (name, age, one trait), places, \
open threads, this month's arc so far.
Respond with JSON only: {{"keywords": [{n} keywords, in topic order], "sentence": "...", "notes": "..."}}"""

DRY_RUN_TEMPLATE = (
    "That morning the radio drifted from {first} to {second}, and she listened without listening, "
    "thinking of {rest}, until the kettle boiled and the ordinary day began."
)


class WriterError(RuntimeError):
    """Every provider and every attempt failed."""


def system_prompt(run_date: str, n: int = 5) -> str:
    return SYSTEM_PROMPT.format(n=n, arc_hint=dates.arc_hint(run_date), notes_max=NOTES_MAX_WORDS)


def _dated(days: list[dict]) -> str:
    return "\n".join(f"{d['date']}: {d['sentence']}" for d in days)


def build_context(book: dict, notes: str, run_date: str, trends: list[str]) -> str:
    """The user message for the writer. Pure.

    Earlier chapters appear only as title + summary. The rehearsal (chapter 0) is never
    shown to chapters 1 and up, and nothing dated on or after run_date is shown.
    """
    chapter = dates.chapter_for(run_date)
    if chapter is None:
        raise ValueError(f"{run_date} is after the end of the book")

    sections = [("NOTES", notes.strip() or "(empty: the story has not started yet; begin your notes)")]

    if chapter != dates.REHEARSAL:
        earlier = [c for c in book["chapters"] if dates.REHEARSAL < c["number"] < chapter]
        text = "\n\n".join(f"Chapter {c['number']}: {c['title']}\n{c['summary']}" for c in earlier)
        sections.append(("EARLIER CHAPTERS", text or "(none)"))

    this_chapter = [d for d in story.chapter_days(book, chapter) if d["date"] < run_date]
    if not this_chapter and chapter > 1:
        previous = [d for d in story.chapter_days(book, chapter - 1) if d["date"] < run_date]
        if previous:
            sections.append(("LAST SENTENCES OF PREVIOUS CHAPTER", _dated(previous[-PREVIOUS_CHAPTER_TAIL:])))

    header = f"THIS CHAPTER ({chapter}, day {dates.day_of_chapter(run_date)} of {dates.days_in_chapter(run_date)})"
    sections.append((header, _dated(this_chapter) or "(no sentences yet)"))

    sections.append((f"TODAY'S TOPICS ({run_date})", "\n".join(f"{i}. {t}" for i, t in enumerate(trends, 1))))
    return "\n\n".join(f"{title}\n{body}" for title, body in sections)


def _clean_reply(reply: dict) -> tuple[list[str], str, str]:
    keywords = reply.get("keywords")
    keywords = [k.strip() for k in keywords if isinstance(k, str)] if isinstance(keywords, list) else []
    sentence = reply.get("sentence")
    sentence = " ".join(sentence.split()).strip("\"“”") if isinstance(sentence, str) else ""
    notes = reply.get("notes")
    if isinstance(notes, (dict, list)):
        notes = json.dumps(notes, ensure_ascii=False, indent=1)
    notes = notes.strip() if isinstance(notes, str) else ""
    return keywords, sentence, notes


def dry_run_day(notes: str, trends: list[str]) -> dict:
    keywords = fallback_keywords(trends)
    ks = keywords or ["silence"]
    rest = ks[2:] or ks[:1]
    listed = rest[0] if len(rest) == 1 else ", of ".join(rest[:-1]) + " and of " + rest[-1]
    sentence = DRY_RUN_TEMPLATE.format(first=ks[0], second=ks[1 % len(ks)], rest=listed)
    return {
        "keywords": keywords,
        "sentence": sentence,
        "notes": notes,
        "writer": DRY_RUN_WRITER,
        "attempts": [],
    }


def write_day(
    book: dict,
    notes: str,
    run_date: str,
    trends: list[str],
    providers: list[Provider] | None = None,
    dry_run: bool = False,
) -> dict:
    """Return {"keywords", "sentence", "notes", "writer", "attempts"} for run_date.

    Raises WriterError when no provider produced a sentence that passes words.check().
    """
    if dry_run:
        return dry_run_day(notes, trends)

    system = system_prompt(run_date, len(trends))
    user = build_context(book, notes, run_date, trends)
    attempts: list[dict] = []

    for provider in providers if providers is not None else default_providers():
        followup: list[dict] = []
        for attempt in range(1, ATTEMPTS_PER_PROVIDER + 1):
            record = {"writer": provider.label, "attempt": attempt}
            attempts.append(record)
            try:
                reply = chat_json(provider, system, user, followup)
            except ValueError as exc:  # the reply was not a JSON object: worth one more try
                record["problems"] = [str(exc)]
                followup = [{"role": "user", "content": "Fix: respond with one JSON object only."}]
                log.warning("%s attempt %d: bad JSON (%s)", provider.label, attempt, exc)
                continue
            except Exception as exc:  # quota, network, auth: try the next provider
                record["error"] = f"{type(exc).__name__}: {exc}"
                log.warning("%s failed (%s); trying the next provider", provider.label, record["error"])
                break

            keywords, sentence, new_notes = _clean_reply(reply)
            record.update(keywords=keywords, sentence=sentence)
            problems = check(trends, keywords, sentence)
            if not problems:
                log.info("%s wrote the sentence on attempt %d", provider.label, attempt)
                return {
                    "keywords": keywords,
                    "sentence": sentence,
                    "notes": new_notes or notes,
                    "writer": provider.label,
                    "attempts": attempts,
                }
            record["problems"] = problems
            log.warning("%s attempt %d failed the check: %s", provider.label, attempt, "; ".join(problems))
            followup = [
                {"role": "assistant", "content": json.dumps(reply, ensure_ascii=False)},
                {"role": "user", "content": "Fix: " + "; ".join(problems) + ". Respond with the full JSON again."},
            ]

    raise WriterError(f"No provider wrote a valid sentence for {run_date}: {json.dumps(attempts, ensure_ascii=False)}")
