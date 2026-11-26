"""The book on disk: docs/story.json (public, read by the page) and the writer's notes.

Days are kept sorted by date and replaced by date, the same pattern as trendy-nft's
gallery. Chapter 0 (the rehearsal) keeps its notes in a separate file.
"""

import json
from datetime import date, timedelta
from pathlib import Path

from book.config import DATA_DIR, DOCS_DIR
from book.dates import END_DATE, REHEARSAL, START_DATE
from book.words import mark

STORY_PATH = DOCS_DIR / "story.json"
WORKING_TITLE = "Working Title"
DAY_FIELDS = ("date", "chapter", "trends", "keywords", "sentence", "writer")
CHAPTER_FIELDS = ("number", "month", "title", "summary")


def empty_story() -> dict:
    return {
        "title": WORKING_TITLE,
        "start": START_DATE.isoformat(),
        "end": END_DATE.isoformat(),
        "chapters": [],
        "days": [],
    }


def load(path: Path = STORY_PATH) -> dict:
    if not path.exists() or not path.read_text().strip():
        return empty_story()
    story = json.loads(path.read_text())
    return {**empty_story(), **story}


def save(story: dict, path: Path = STORY_PATH) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(story, indent=2, ensure_ascii=False) + "\n")


def has_day(story: dict, date: str) -> bool:
    return any(d.get("date") == date for d in story["days"])


def get_day(story: dict, date: str) -> dict | None:
    return next((d for d in story["days"] if d.get("date") == date), None)


def add_day(story: dict, day: dict) -> dict:
    """Insert or replace the day by its date and keep the days sorted. Returns the story."""
    entry = {key: day[key] for key in DAY_FIELDS}
    story["days"] = sorted(
        [d for d in story["days"] if d.get("date") != entry["date"]] + [entry],
        key=lambda d: d["date"],
    )
    return story


def chapter_days(story: dict, number: int) -> list[dict]:
    return [d for d in story["days"] if d.get("chapter") == number]


def get_chapter(story: dict, number: int) -> dict | None:
    return next((c for c in story["chapters"] if c.get("number") == number), None)


def set_chapter(story: dict, number: int, month: str, title: str, summary: str) -> dict:
    """Insert or replace a closed chapter's title and summary, sorted by number."""
    entry = {"number": number, "month": month, "title": title, "summary": summary}
    story["chapters"] = sorted(
        [c for c in story["chapters"] if c.get("number") != number] + [entry],
        key=lambda c: c["number"],
    )
    return story


# --- notes --------------------------------------------------------------------------


def notes_path(chapter: int, data_dir: Path = DATA_DIR) -> Path:
    return data_dir / ("notes-rehearsal.md" if chapter == REHEARSAL else "notes.md")


def load_notes(chapter: int, data_dir: Path = DATA_DIR) -> str:
    path = notes_path(chapter, data_dir)
    return path.read_text().strip() if path.exists() else ""


def save_notes(chapter: int, text: str, data_dir: Path = DATA_DIR) -> Path:
    path = notes_path(chapter, data_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text.strip() + "\n")
    return path


# --- plain-text view ------------------------------------------------------------------


GAP = "▒ signal lost ▒"


def _dates_between(first: str, last: str) -> list[str]:
    start, end = date.fromisoformat(first), date.fromisoformat(last)
    return [(start + timedelta(days=i)).isoformat() for i in range((end - start).days + 1)]


def render_text(story: dict, chapter: int | None = None) -> str:
    """The book as plain text, keywords in [brackets], missing days shown as gaps.

    chapter=None shows every chapter of the book proper; chapter 0 must be asked for.
    """
    if chapter is None:
        numbers = sorted({d["chapter"] for d in story["days"]} | {c["number"] for c in story["chapters"]})
        numbers = [n for n in numbers if n != REHEARSAL]
    else:
        numbers = [chapter]

    lines = [story["title"].upper(), ""]
    for number in numbers:
        info = get_chapter(story, number)
        name = "REHEARSAL" if number == REHEARSAL else f"CHAPTER {number:02d}"
        lines.append(f"{name} // {info['title']}" if info else f"{name} // IN PROGRESS")
        if info:
            lines.append(info["summary"])
        lines.append("")
        days = {d["date"]: d for d in chapter_days(story, number)}
        if days:
            first = min(days) if number == REHEARSAL else min(days)[:8] + "01"
            for d in _dates_between(first, max(days)):
                day = days.get(d)
                lines.append(f"{d}  {mark(day['sentence'], day['keywords']) if day else GAP}")
        else:
            lines.append("(no days yet)")
        lines.append("")
    if not numbers:
        lines.append("(no chapters yet; try --chapter 0 for the rehearsal)")
    return "\n".join(lines).rstrip() + "\n"
