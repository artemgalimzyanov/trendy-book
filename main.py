"""Trendy Book CLI: run each step of the daily sentence on its own, or the whole day.

Examples:
  python main.py trends [--dry-run]
  python main.py dates [--date 2027-02-28]
  python main.py llm-check
  python main.py show [--chapter N] [--file docs/story.sample.json]
  python main.py write --trends "a,b,c,d,e" [--date 2026-12-05] [--dry-run] [--context]
  python main.py chapter --close N [--dry-run] [--save]
  python main.py run [--date 2026-12-05] [--trends "a,b,c,d,e"] [--dry-run] [--force]
  python main.py sample
  python main.py serve [--port 8000]
"""

import argparse
import json
import logging
import sys
import time
from pathlib import Path

from book import chapter, dates, llm, pipeline, sample, story, trends, words, writer
from book.config import has_env
from book.config import DOCS_DIR, output_dir_for

# `run --sandbox` keeps its story and notes here (gitignored, but served by `serve`),
# so real runs for any date can be tried without touching docs/story.json or data/.
SANDBOX_DIR = DOCS_DIR / "sandbox"


def _split_trends(value: str | None) -> list[str] | None:
    """Comma-separated trends, or semicolon-separated when a trend itself has commas."""
    if not value:
        return None
    separator = ";" if ";" in value else ","
    return [t.strip() for t in value.split(separator) if t.strip()]


def cmd_trends(args) -> int:
    result = trends.get_trends(n=args.n, dry_run=args.dry_run)
    out = output_dir_for(dates.today_utc()) / "trends.json"
    out.write_text(json.dumps(result, indent=2, ensure_ascii=False))
    for t in result:
        print(t)
    print(f"\nSaved to {out}", file=sys.stderr)
    return 0


def cmd_dates(args) -> int:
    d = args.date or dates.today_utc()
    chapter = dates.chapter_for(d)
    print(f"date:     {d}")
    if chapter is None:
        print("chapter:  none (the book is complete)")
        return 0
    label = "0 (rehearsal)" if chapter == dates.REHEARSAL else str(chapter)
    print(f"chapter:  {label}  [{dates.chapter_month(d)}]")
    print(f"day:      {dates.day_of_chapter(d)} of {dates.days_in_chapter(d)}")
    if chapter != dates.REHEARSAL:
        print(f"book day: {dates.book_day(d)} of {dates.book_length()}")
    print(f"chapter end: {'yes' if dates.is_chapter_end(d) else 'no'}")
    print(f"book end:    {'yes' if dates.is_book_end(d) else 'no'}")
    print(f"arc hint: {dates.arc_hint(d)}")
    return 0


def cmd_llm_check(args) -> int:
    """List Gemini flash models and send a tiny JSON ping to each writer provider."""
    if has_env("GEMINI_API_KEY"):
        try:
            models = sorted(m.id for m in llm.gemini_provider().client.models.list() if "flash" in m.id)
            print("Gemini flash models:")
            for m in models:
                mark = "  <- GEMINI_MODEL" if m.removeprefix("models/") == llm.GEMINI_MODEL else ""
                print(f"  {m}{mark}")
        except Exception as exc:
            print(f"Gemini model list failed: {exc}")
    else:
        print("GEMINI_API_KEY not set: Gemini is skipped (get one at https://aistudio.google.com/apikey)")

    ok = True
    for provider in llm.providers():
        started = time.monotonic()
        try:
            reply = llm.chat_json(provider, 'Reply with JSON only: {"ok": true}.', "ping")
            status = "OK" if reply.get("ok") is True else f"ODD REPLY {reply}"
        except Exception as exc:
            status, ok = f"FAIL {type(exc).__name__}: {exc}", False
        json_mode = "json mode" if provider.json_mode else "fence stripping"
        print(f"{provider.label:32} {status}  ({time.monotonic() - started:.1f}s, {json_mode})")
    return 0 if ok else 1


def cmd_show(args) -> int:
    book = story.load(Path(args.file)) if args.file else story.load()
    print(story.render_text(book, args.chapter), end="")
    return 0


def cmd_write(args) -> int:
    """Write one sentence for the given trends and print it. Nothing is saved."""
    run_date = args.date or dates.today_utc()
    chapter = dates.chapter_for(run_date)
    if chapter is None:
        print("The book is complete.")
        return 1
    topics = _split_trends(args.trends)
    book, notes = story.load(), story.load_notes(chapter)
    if args.context:
        print("=== SYSTEM\n" + writer.system_prompt(run_date, len(topics)))
        print("\n=== USER\n" + writer.build_context(book, notes, run_date, topics) + "\n")
    result = writer.write_day(book, notes, run_date, topics, dry_run=args.dry_run)
    for a in result["attempts"][:-1]:
        print(f"[{a['writer']} attempt {a['attempt']}] {a.get('error') or '; '.join(a.get('problems', []))}")
    print(f"{run_date}  chapter {chapter}, day {dates.day_of_chapter(run_date)}  ({result['writer']})")
    print(f"keywords: {', '.join(result['keywords'])}")
    print(f"words:    {words.count_words(result['sentence'])}")
    print()
    print(words.mark(result["sentence"], result["keywords"]))
    print("\n--- notes\n" + result["notes"])
    return 0


def cmd_chapter(args) -> int:
    """Title and summary for a chapter; --save writes them to docs/story.json."""
    number = args.close
    book = story.load()
    final = number == dates.END_DATE.month
    result = chapter.close_chapter(book, number, story.load_notes(number), final=final, dry_run=args.dry_run)
    print(f"CHAPTER {number:02d} // {result['title']}  ({result['writer']})")
    print(result["summary"])
    if final:
        print(f"\nBook title: {result['book_title']}")
    if args.save and not args.dry_run:
        story.save(chapter.apply_close(book, number, result))
        print(f"\nSaved to {story.STORY_PATH}", file=sys.stderr)
    elif args.save:
        print("\n(dry run: not saved)", file=sys.stderr)
    return 0


def cmd_run(args) -> int:
    paths = {"story_path": SANDBOX_DIR / "story.json", "data_dir": SANDBOX_DIR} if args.sandbox else {}
    result = pipeline.run(
        run_date=args.date,
        trends=_split_trends(args.trends),
        dry_run=args.dry_run,
        force=args.force,
        n=args.n,
        **paths,
    )
    print(json.dumps(result, indent=2, ensure_ascii=False))
    if args.sandbox and not args.dry_run:
        rel = (SANDBOX_DIR / "story.json").relative_to(DOCS_DIR.parent)
        print(f"\nSandbox: {rel}  (read: main.py show --file {rel})")
        print(f"Page: main.py serve, then http://localhost:8000/?data=sandbox/story.json&today={result['date']}")
    return 0


def cmd_sample(args) -> int:
    path = sample.write()
    print(f"Wrote {path}  (open http://localhost:8000/?data=story.sample.json after `main.py serve`)")
    return 0


def cmd_serve(args) -> int:
    import http.server
    from functools import partial

    handler = partial(http.server.SimpleHTTPRequestHandler, directory=str(DOCS_DIR))
    print(f"Serving {DOCS_DIR} at http://localhost:{args.port}  (Ctrl+C to stop)")
    http.server.ThreadingHTTPServer(("", args.port), handler).serve_forever()
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Trendy Book: world news -> one sentence a day -> a novel")
    parser.add_argument("-v", "--verbose", action="store_true", help="debug logging")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("trends", help="fetch today's top trends")
    p.add_argument("--n", type=int, default=trends.DEFAULT_COUNT, help="how many trends")
    p.add_argument("--dry-run", action="store_true", help="skip the model, use raw headlines")
    p.set_defaults(func=cmd_trends)

    p = sub.add_parser("dates", help="show the chapter, day number and arc hint for a date")
    p.add_argument("--date", help="ISO date (default today, UTC)")
    p.set_defaults(func=cmd_dates)

    p = sub.add_parser("llm-check", help="list Gemini models and ping each writer provider")
    p.set_defaults(func=cmd_llm_check)

    p = sub.add_parser("show", help="print the story, keywords in [brackets]")
    p.add_argument("--chapter", type=int, help="only this chapter (0 = rehearsal)")
    p.add_argument("--file", help="another story file (default docs/story.json)")
    p.set_defaults(func=cmd_show)

    p = sub.add_parser("write", help="write one sentence for given trends (prints it, saves nothing)")
    p.add_argument("--trends", required=True, help='comma-separated, e.g. "a,b,c,d,e" (or ";" if trends contain commas)')
    p.add_argument("--date", help="ISO date (default today, UTC)")
    p.add_argument("--dry-run", action="store_true", help="template sentence, no model call")
    p.add_argument("--context", action="store_true", help="also print the prompt sent to the model")
    p.set_defaults(func=cmd_write)

    p = sub.add_parser("chapter", help="title + summary for a chapter")
    p.add_argument("--close", type=int, required=True, metavar="N", help="chapter number (0 = rehearsal)")
    p.add_argument("--dry-run", action="store_true", help="template title and summary, no model call")
    p.add_argument("--save", action="store_true", help="write the result to docs/story.json")
    p.set_defaults(func=cmd_chapter)

    p = sub.add_parser("run", help="the whole day: trends -> sentence -> story.json (+ chapter close)")
    p.add_argument("--date", help="ISO date (default today, UTC)")
    p.add_argument("--n", type=int, default=trends.DEFAULT_COUNT, help="how many trends")
    p.add_argument("--trends", help='skip fetching; use these (comma- or ";"-separated)')
    p.add_argument("--dry-run", action="store_true", help="no paid calls; only output/<date>/ is written")
    p.add_argument("--force", action="store_true", help="redo the day even if it is already written")
    p.add_argument("--sandbox", action="store_true",
                   help="real run, but into docs/sandbox/ (gitignored) instead of docs/story.json and data/")
    p.set_defaults(func=cmd_run)

    p = sub.add_parser("sample", help="write offline sample data to docs/story.sample.json")
    p.set_defaults(func=cmd_sample)

    p = sub.add_parser("serve", help="preview the book page locally")
    p.add_argument("--port", type=int, default=8000)
    p.set_defaults(func=cmd_serve)

    return parser


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(levelname)s %(name)s: %(message)s",
        stream=sys.stderr,
    )
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
