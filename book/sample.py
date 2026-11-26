"""Offline sample data for the page: 75 days, 2 closed chapters, 1 in progress, 1 gap.

Deterministic and model-free; every sample sentence passes words.check().
"""

from datetime import date, timedelta
from pathlib import Path

from book import dates, story
from book.config import DOCS_DIR

SAMPLE_PATH = DOCS_DIR / "story.sample.json"
SAMPLE_DAYS = 75  # 2027-01-01 .. 2027-03-16
GAP_DATE = "2027-02-14"
WRITER = "sample"

# (topic, keyword): generic topics, no real people
TOPICS = [
    ("Central bank holds interest rates", "interest"), ("Arctic heatwave breaks records", "Arctic"),
    ("Marathon world record falls", "Marathon"), ("Chip export ban talks", "Chip"),
    ("Ferry strike halts crossings", "strike"), ("Flood warnings across river delta", "Flood"),
    ("Satellite launch delayed again", "Satellite"), ("Wildfire smoke reaches capital", "smoke"),
    ("Grain corridor deal extended", "Grain"), ("Election recount ordered", "recount"),
    ("Museum returns looted bronzes", "bronzes"), ("Volcano eruption grounds flights", "Volcano"),
    ("Teachers march over pay", "Teachers"), ("Coral reef bleaching spreads", "Coral"),
    ("Ceasefire talks resume", "Ceasefire"), ("Power grid blackout hits millions", "blackout"),
    ("Bird flu found on farms", "flu"), ("Rare comet visible tonight", "comet"),
    ("Shipping lane piracy rises", "piracy"), ("Lithium mine protest grows", "Lithium"),
    ("Earthquake shakes coastal towns", "Earthquake"), ("Space station crew returns", "crew"),
    ("Drought threatens coffee harvest", "coffee"), ("Football final ends in penalties", "penalties"),
    ("Housing prices fall sharply", "Housing"), ("Glacier collapse blocks valley", "Glacier"),
    ("Census shows shrinking villages", "villages"), ("Bank merger blocked by regulators", "merger"),
    ("Fishing quota dispute escalates", "quota"), ("Train derailment injures dozens", "Train"),
    ("New antibiotic approved", "antibiotic"), ("Border crossing reopens", "Border"),
    ("Storm surge floods harbour", "harbour"), ("Opera house reopens after fire", "Opera"),
    ("Refinery fire sends oil higher", "oil"), ("Students protest exam reform", "exam"),
    ("Monsoon arrives early", "Monsoon"), ("Diplomats expelled in spy row", "spy"),
    ("Ancient shipwreck discovered", "shipwreck"), ("Heat pump subsidy scrapped", "subsidy"),
    ("Snowstorm strands drivers on motorway", "Snowstorm"),
]

PROPER = {"Arctic"}  # keywords that keep their capital inside a sentence

TEMPLATES = [
    "Mara left the clinic after midnight, the {0} story still on her phone, and on the tram she "
    "heard two men argue about the {1}, the {2} and the {3} until her stop, where the {4} posters had faded.",
    "Teodor fixed the ferry engine by lamplight while the radio drifted from the {0} to the {1}, and "
    "he thought of his sister, of the {2}, of the {3} and, for no reason at all, of the {4}.",
    "In the kitchen Ines spread the newspaper over the table, so the {0} and the {1} soaked up the "
    "spilled tea, and the {2}, the {3} and the {4} were folded away with the bread.",
    "Nobody at the harbour mentioned the {0} or the {1}, but Mara noticed how the old men went quiet "
    "when the screen above the bar showed the {2}, then the {3}, then the {4}.",
    "That evening the three of them ate on the balcony and said nothing about the {0}, the {1}, the "
    "{2} or the {3}, though the {4} glowed on every screen across the street.",
    "Teodor wrote Mara a letter he never sent, about the {0} and the {1}, about the {2} he remembered "
    "from boyhood, and about how the {3} and the {4} made everything feel temporary.",
    "Mara counted the hours of her night shift by the bulletins: the {0} at ten, the {1} at eleven, "
    "the {2} at midnight, the {3} at one, and the {4} just before dawn.",
    "Ines told the neighbour's children a story in which the {0}, the {1} and the {2} were only the "
    "names of streets, and the {3} and the {4} were two dogs who never learned to sit.",
    "On the ferry Mara watched a stranger read about the {0}, fold the paper at the {1}, frown at the "
    "{2}, and leave it on the seat, open at the {3} and the {4}.",
    "The landlord raised the rent and blamed the {0}, the {1} and the {2}, and Teodor, who had heard "
    "it all before, blamed the {3} and then, quietly, the {4}.",
]

CHAPTERS = [
    (1, "The Ferry in Winter",
     "Mara, a night-shift nursing student, and her uncle Teodor, a ferry mechanic, shared a cold flat "
     "above the harbour while the news arrived in fragments through radios and phone screens. Ines, "
     "their neighbour, kept the building together with tea and stories. A stranger on the morning "
     "ferry began to appear too often, always reading, always leaving the paper behind. By the end "
     "of January Mara had started keeping the papers, and Teodor had stopped asking why."),
    (2, "Rent and Weather",
     "February brought a rent rise that Teodor could not cover and a storm that kept the ferries in "
     "port for a week. Mara took extra shifts and found a name written in the margin of one of the "
     "stranger's newspapers. Ines fell ill and recovered, though she now forgot the endings of her "
     "stories. On the last night of the month, Mara followed the stranger off the ferry and lost him "
     "in the fog behind the fish market, holding a key that was not hers."),
]


def build() -> dict:
    book = story.empty_story()
    for i in range(SAMPLE_DAYS):
        d = (dates.START_DATE + timedelta(days=i)).isoformat()
        if d == GAP_DATE:
            continue
        picks = [TOPICS[(i * 7 + k * 8) % len(TOPICS)] for k in range(5)]
        template = TEMPLATES[(i * 3) % len(TEMPLATES)]
        keywords = [kw for _, kw in picks]
        sentence = template.format(*(kw if kw in PROPER else kw.lower() for kw in keywords))
        story.add_day(book, {
            "date": d,
            "chapter": dates.chapter_for(d),
            "trends": [t for t, _ in picks],
            "keywords": keywords,
            "sentence": sentence,
            "writer": WRITER,
        })
    for number, title, summary in CHAPTERS:
        story.set_chapter(book, number, date(dates.START_DATE.year, number, 1).strftime("%Y-%m"), title, summary)
    return book


def write(path: Path = SAMPLE_PATH) -> Path:
    story.save(build(), path)
    return path
