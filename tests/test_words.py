import pytest

from book import words

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


def test_good_sentence_has_no_problems():
    assert words.check(TRENDS, KEYWORDS, SENTENCE) == []


# --- fallback keywords -----------------------------------------------------------


def test_fallback_prefers_longest_proper_noun_and_skips_stopwords():
    assert words.fallback_keywords(TRENDS) == ["Kenya", "German", "Black", "French", "Bolsonaro"]  # ties: first word wins
    assert words.fallback_keywords(["Norway state funeral for King Harald"]) == ["Norway"]
    assert words.fallback_keywords(["Talks about the tariffs"]) == ["Talks"]


def test_fallback_without_proper_nouns_takes_longest_word():
    assert words.fallback_keywords(["rising sea levels threaten islands"]) == ["threaten"]


def test_fallback_strips_possessives_and_keeps_acronyms():
    assert words.fallback_keywords(["Trump's tariff plan"]) == ["Trump"]
    assert words.fallback_keywords(["UN vote on aid"]) == ["UN"]


def test_fallback_is_deterministic_and_always_in_its_trend():
    trends = TRENDS + ["US announces new tariffs on host of countries including China"]
    first = words.fallback_keywords(trends)
    assert first == words.fallback_keywords(trends)
    assert all(words.in_trend(k, t) for k, t in zip(first, trends))


# --- keywords in their trends ------------------------------------------------------


def test_keyword_must_be_a_whole_word_of_its_own_trend():
    problems = words.check(TRENDS, ["Ebola", "spy", "Sea ship", "stud", "Brazil"], SENTENCE)
    assert any("'stud' does not appear exactly in topic 4" in p for p in problems)
    assert not any("'Sea ship'" in p and "topic" in p for p in problems)


def test_keyword_from_the_wrong_trend_fails():
    swapped = ["spy", "Ebola", "Black Sea", "student", "Bolsonaro"]
    problems = words.check(TRENDS, swapped, SENTENCE)
    assert any("'spy' does not appear exactly in topic 1" in p for p in problems)


def test_wrong_keyword_count_and_too_long_keyword():
    assert any("exactly 5 keywords" in p for p in words.check(TRENDS, KEYWORDS[:4], SENTENCE))
    long_kw = ["Kenya first Ebola"] + KEYWORDS[1:]
    assert any("too long" in p for p in words.check(TRENDS, long_kw, SENTENCE))


# --- keywords in the sentence ------------------------------------------------------


def test_missing_keyword_is_reported():
    sentence = SENTENCE.replace("Ebola", "the outbreak")
    assert words.check(TRENDS, KEYWORDS, sentence) == ["the sentence must contain the keyword(s): 'Ebola'"]


@pytest.mark.parametrize(
    "keyword, sentence, found",
    [
        ("strike", "She watched the strikes spread.", True),
        ("Bolsonaro", "Bolsonaro’s grin was everywhere.", True),
        ("spy", "Two spies met.", True),
        ("bus", "The buses were late.", True),
        ("Black Sea", "Ships crossed the black  sea at dawn.", True),
        ("ship", "The relationship ended.", False),
        ("art", "She started again.", False),
        ("Sea", "Seattle was grey.", False),
    ],
)
def test_keyword_in_sentence_allows_plurals_and_possessives_only(keyword, sentence, found):
    assert words.in_sentence(keyword, sentence) is found


# --- shape of the sentence -----------------------------------------------------------


def test_word_count_limits():
    short = "Ebola, a spy, the Black Sea, a student and Bolsonaro met."
    assert any("words; write 20 to 50" in p for p in words.check(TRENDS, KEYWORDS, short))
    long = SENTENCE[:-1] + ", and" + " then she kept walking" * 10 + "."
    assert any("words; write 20 to 50" in p for p in words.check(TRENDS, KEYWORDS, long))


def test_newline_is_a_problem():
    broken = SENTENCE.replace("watched a stranger", "watched\na stranger")
    assert "no line breaks; write one single sentence" in words.check(TRENDS, KEYWORDS, broken)


def test_two_sentences_are_a_problem():
    two = SENTENCE.replace("café, wondering", "café. She wondered")
    assert "write exactly one sentence; it reads as two or more" in words.check(TRENDS, KEYWORDS, two)


@pytest.mark.parametrize(
    "sentence",
    [
        "Mr. Okafor and Dr. Lin walked down St. Mark's road to the U.S. embassy at 9 a.m. today.",
        "Mrs. Patel read J. K. Rowling on the bus.",
        "She asked whether anyone had seen the ship?",
        "He said “nothing ever changes here.”",
    ],
)
def test_abbreviations_and_quotes_are_still_one_sentence(sentence):
    assert words.sentence_count_problem(sentence) is None


def test_sentence_needs_final_punctuation():
    assert "full stop" in words.sentence_count_problem("She walked home")


def test_relaxed_rule_accepts_four_of_five(monkeypatch):
    monkeypatch.setattr(words, "REQUIRED_IN_SENTENCE", 4)
    sentence = SENTENCE.replace("Ebola", "the outbreak")
    assert words.check(TRENDS, KEYWORDS, sentence) == []
