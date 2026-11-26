# Trendy Book

**A novel written one sentence a day from the world's news, 1 Jan to 31 Dec 2027.**

Every day, the five most widely covered world-news topics are turned into the next
sentence of a literary novel. One keyword from each topic must appear in the sentence.
Each calendar month is one chapter, so the finished book has 12 chapters.

Work in progress. A sister project of [trendy-nft](https://github.com/artemgalimzyanov/trendy-nft).

## Quick start

```bash
/opt/homebrew/bin/python3.12 -m venv .venv
.venv/bin/pip install -r requirements-dev.txt
cp .env.example .env   # then fill in the keys
.venv/bin/python main.py --help
.venv/bin/python -m pytest
```

## Commands

```bash
.venv/bin/python main.py trends [--dry-run]                 # today's 5 topics
.venv/bin/python main.py dates --date 2027-02-28             # chapter, day, arc hint
.venv/bin/python main.py llm-check                           # Gemini models + ping each writer
.venv/bin/python main.py write --trends "a,b,c,d,e" [--dry-run] [--context]   # prints, saves nothing
.venv/bin/python main.py run [--date …] [--trends …] [--dry-run] [--force]    # the whole day
.venv/bin/python main.py chapter --close N [--dry-run] [--save]
.venv/bin/python main.py show [--chapter N]                  # the story, keywords in [brackets]
.venv/bin/python main.py sample && .venv/bin/python main.py serve
# then open http://localhost:8000/?data=story.sample.json
```

`--trends` takes commas, or semicolons when a trend itself contains a comma.
