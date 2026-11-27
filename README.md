# Trendy Book

**A novel written one sentence a day from what the world is talking about.**

👉 Read the book: [artemgalimzyanov.github.io/trendy-book](https://artemgalimzyanov.github.io/trendy-book/) (the first sentence arrives on 1 January 2027)

## The idea

We are surrounded by daily news and endless noise. A story takes over every screen for a day or two, and a week later it is forgotten. Read one headline at a time, the news can feel like a stream of unconnected shocks.

This project tries a different way to read it: as a novel. Every day, the five biggest world stories become the next sentence of a book. A word from each story has to appear in that sentence, so the news can't be skipped. But the novel isn't about the news. It follows ordinary, fictional people, and the headlines reach them the way they reach the rest of us: in the background of their lives.

The book is written over one year, from 1 January to 31 December 2027. Each month is a chapter, so the finished novel has 12 chapters and 365 sentences. Past sentences never change. There is no outline and no list of characters made in advance. The characters and the plot grow out of the story itself, and the AI writer keeps its own running notes, so tomorrow's sentence knows what happened today. At the end of each month the chapter gets a title and a summary, and on the last day of the year the book gets its name. Until then it is called "Working Title".

The whole book lives in this repository as a single file, and the git history keeps a record of every day it was written. The reading page is styled like a cyberpunk terminal. The newest sentence types itself out, the news keywords glow, and tapping any sentence shows the five news topics it came from. A missed day stays in the book as a visible gap: "signal lost". When the year is over, the page becomes the finished novel, which can also be saved as a PDF.

Trendy Book is a sister project of [Trendy](https://github.com/artemgalimzyanov/trendy-nft), which turns the same daily news into a cartoon.

## How it works

The pipeline runs automatically once a day:

```
world news → top 5 topics → 5 keywords → one sentence → check → story file → reading page
```

1. **Get the trends.** Headlines are collected from about 20 news outlets across North
   America, Europe, the Middle East, Asia, Africa, Latin America and Oceania. A small
   language model picks the 5 stories that the most outlets are covering, so no single
   country or outlet sets the agenda.
2. **Write the sentence.** An AI writer (OpenAI's GPT-5.4 mini, with Google's Gemini as a backup) reads its
   notes, the summaries of earlier chapters, this month's sentences so far and the day's
   5 topics. It picks a keyword of one or two words from each topic, writes the next
   sentence of the novel (20 to 50 words) and updates its notes. It also gets a hint about
   where the month is in its story: build the situation in the first ten days, complicate
   it in the next ten, move toward a turning point, and resolve it in the last three days.
3. **Check it.** Code checks that each keyword really comes from its topic, that every
   keyword appears in the sentence, and that the reply is a single sentence of the right
   length. If something is wrong, the writer is told what to fix and tries again. If it
   still fails, the backup model takes over.
4. **Save it.** The sentence, its keywords and its topics are added to `docs/story.json`,
   and the notes to `data/notes.md`. A GitHub Actions job does all of this at 06:00 UTC
   and commits the result. Two later runs each day try again if the first one failed.
5. **Close the chapter.** On the last day of each month, the writer reads the whole
   chapter and gives it a title and a short summary. Later chapters see earlier ones only
   through these summaries, which keeps the writer's prompt small all year. On
   31 December 2027 it also names the book.
6. **Publish.** GitHub Pages serves the reading page straight from the repository, so each
   new sentence appears on the site a minute or two after it is committed.

## What's next

- **December 2026: the rehearsal.** The whole pipeline runs for a month on real news as a
  hidden "chapter 0", to tune the writer before launch. It never appears on the page, and
  the writer never sees it once the real book begins.
- **1 January 2027: the first sentence.**
- **31 December 2027: the last sentence.** The final chapter closes, the book gets its
  title, and the page becomes the finished novel.
