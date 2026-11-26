"""Keyword rules for the daily sentence. Pure: no I/O, no model.

check() returns a list of human-readable problems; an empty list means the sentence
passes. The problems are sent back to the model verbatim as "Fix: ...".
"""

import re

MIN_WORDS, MAX_WORDS = 15, 60  # looser than the prompt's 20-50, so near misses still pass
MAX_KEYWORD_WORDS = 2  # "one word, or a name of up to two words"
# How many of the keywords must appear in the sentence. Lower to 4 to relax the rule.
REQUIRED_IN_SENTENCE = 5

STOPWORDS = frozenset(
    """
    a about above after again against ahead all almost also amid among an and any are as at
    back be been before being below between both but by can could did do does down during
    each else few first for from further get gets had has have he her here hers him his how
    if in into is it its just last least less like made make makes many may more most much
    must near new news next no nor not now of off on once one only or other our out over own
    per said say says see seen set she should since so some still such than that the their
    them then there these they this those through to too top under until up upon us very
    via was we were what when where which while who whom why will with without would year
    years yet you your
    """.split()
)

TITLES = ("Mr", "Mrs", "Ms", "Dr", "St", "Jr", "Sr", "Prof", "Gen", "Col", "Lt", "Sgt", "Capt", "Rev", "Mt", "No")

_TOKEN = re.compile(r"[^\W_][\w'’-]*", re.UNICODE)
_POSSESSIVE = re.compile(r"['’]s?$")
_ABBREVIATIONS = [
    re.compile(r"\b(?:%s)\." % "|".join(TITLES)),  # Mr. Dr. St.
    re.compile(r"\b(?:[A-Za-z]\.){2,}"),  # U.S. e.g. a.m.
    re.compile(r"(?<![\w.])[A-Z]\.(?=\s)"),  # initials: J. K. Rowling
]
_BOUNDARY = re.compile(r"[.!?…]+[\"”’)\]]*\s+[\"“‘(\[]*[A-Z0-9]")
_ENDING = re.compile(r"[.!?…][\"”’)\]]*$")


# --- fallback keywords ---------------------------------------------------------


def _tokens(text: str) -> list[str]:
    return [_POSSESSIVE.sub("", t).strip("-") for t in _TOKEN.findall(text)]


def _is_proper(word: str) -> bool:
    return word[:1].isupper()


def _keyword_for(trend: str) -> str:
    words = [w for w in _tokens(trend) if w and w.lower() not in STOPWORDS and not w.isdigit()]
    words = [w for w in words if len(w) >= 3 or w.isupper()]
    if not words:
        tokens = _tokens(trend)
        return tokens[0] if tokens else trend.strip()
    proper = [w for w in words if _is_proper(w)]
    pool = proper or words
    return max(pool, key=len)  # max() keeps the first of equally long words


def fallback_keywords(trends: list[str]) -> list[str]:
    """One keyword per trend without a model: the longest proper noun, else the longest word."""
    return [_keyword_for(t) for t in trends]


# --- the check -----------------------------------------------------------------


def _phrase(keyword: str) -> str:
    return r"\s+".join(re.escape(part) for part in keyword.split())


def in_trend(keyword: str, trend: str) -> bool:
    """The keyword appears in the trend as a whole word or phrase (any case)."""
    if not keyword.strip():
        return False
    return re.search(rf"(?<!\w){_phrase(keyword)}(?!\w)", trend, re.IGNORECASE) is not None


def _sentence_pattern(keyword: str) -> str:
    forms = [_phrase(keyword)]
    if len(keyword) > 2 and keyword[-1] in "yY" and keyword[-2].lower() not in "aeiou":
        forms.append(_phrase(keyword[:-1]) + "ies")  # spy -> spies
    suffix = r"(?:['’]s|s['’]|es|s|['’])?"
    return rf"(?<!\w)(?:{'|'.join(forms)}){suffix}(?!\w)"


def in_sentence(keyword: str, sentence: str) -> bool:
    """The keyword appears as a whole word; plurals and possessives are allowed."""
    keyword = keyword.strip()
    if not keyword:
        return False
    return re.search(_sentence_pattern(keyword), sentence, re.IGNORECASE) is not None


def mark(sentence: str, keywords: list[str], before: str = "[", after: str = "]") -> str:
    """Wrap every keyword occurrence (with its plural/possessive ending) in markers."""
    keywords = sorted({k.strip() for k in keywords if isinstance(k, str) and k.strip()}, key=len, reverse=True)
    if not keywords:
        return sentence
    pattern = "|".join(_sentence_pattern(k) for k in keywords)
    return re.sub(pattern, lambda m: f"{before}{m.group(0)}{after}", sentence, flags=re.IGNORECASE)


def count_words(sentence: str) -> int:
    return sum(1 for token in sentence.split() if re.search(r"\w", token))


def _mask_abbreviations(sentence: str) -> str:
    for pattern in _ABBREVIATIONS:
        sentence = pattern.sub(lambda m: m.group(0).replace(".", "·"), sentence)
    return sentence


def sentence_count_problem(sentence: str) -> str | None:
    masked = _mask_abbreviations(sentence.strip())
    if _BOUNDARY.search(masked):
        return "write exactly one sentence; it reads as two or more"
    if not _ENDING.search(masked):
        return "end the sentence with a full stop, question mark or exclamation mark"
    return None


def check(trends: list[str], keywords: list[str], sentence: str) -> list[str]:
    """Every problem with today's keywords and sentence, as short instructions."""
    problems: list[str] = []
    keywords = [k.strip() if isinstance(k, str) else "" for k in (keywords or [])]
    sentence = sentence if isinstance(sentence, str) else ""

    if len(keywords) != len(trends):
        problems.append(f"give exactly {len(trends)} keywords, one per topic in topic order; got {len(keywords)}")

    for i, (trend, keyword) in enumerate(zip(trends, keywords), 1):
        if not keyword:
            problems.append(f"keyword {i} is empty; pick one word from topic {i} ({trend!r})")
        elif len(keyword.split()) > MAX_KEYWORD_WORDS:
            problems.append(f"keyword {keyword!r} is too long; use one word or a name of up to {MAX_KEYWORD_WORDS} words")
        elif not in_trend(keyword, trend):
            problems.append(f"keyword {keyword!r} does not appear exactly in topic {i} ({trend!r})")

    present = [k for k in keywords if k and in_sentence(k, sentence)]
    missing = [k for k in keywords if k and not in_sentence(k, sentence)]
    if missing and len(present) < min(REQUIRED_IN_SENTENCE, len(keywords)):
        problems.append("the sentence must contain the keyword(s): " + ", ".join(repr(k) for k in missing))

    n = count_words(sentence)
    if not MIN_WORDS <= n <= MAX_WORDS:
        problems.append(f"the sentence has {n} words; write 20 to 50")
    if "\n" in sentence.strip():
        problems.append("no line breaks; write one single sentence")
    if sentence.strip():
        one = sentence_count_problem(sentence)
        if one:
            problems.append(one)
    return problems
