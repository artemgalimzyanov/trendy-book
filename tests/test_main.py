import main
from book import pipeline, story


def test_run_sandbox_writes_only_the_sandbox(tmp_path, monkeypatch, capsys):
    real_story, real_data = tmp_path / "docs" / "story.json", tmp_path / "data"
    sandbox = tmp_path / "docs" / "sandbox"
    monkeypatch.setattr(story, "STORY_PATH", real_story)
    monkeypatch.setattr(pipeline, "DATA_DIR", real_data)
    monkeypatch.setattr(main, "SANDBOX_DIR", sandbox)
    monkeypatch.setattr(main, "DOCS_DIR", tmp_path / "docs")
    monkeypatch.setattr(pipeline, "output_dir_for", lambda d: (tmp_path / "output" / d).mkdir(parents=True, exist_ok=True) or tmp_path / "output" / d)
    monkeypatch.setattr(pipeline, "write_day", lambda book, notes, run_date, trends, **kw: {
        "keywords": ["a"] * 5, "sentence": "S.", "notes": "n", "writer": "gemini:test", "attempts": []})

    assert main.main(["run", "--sandbox", "--date", "2027-01-01", "--trends", "a;b;c;d;e"]) == 0

    assert story.has_day(story.load(sandbox / "story.json"), "2027-01-01")
    assert (sandbox / "notes.md").read_text().strip() == "n"
    assert not real_story.exists() and not real_data.exists()
    assert "?data=sandbox/story.json&today=2027-01-01" in capsys.readouterr().out
