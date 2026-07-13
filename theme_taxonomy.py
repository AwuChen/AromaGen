import csv
import json
from collections import Counter
from pathlib import Path

import matplotlib.pyplot as plt

ROOT = Path(__file__).resolve().parent
INPUT_PATH = ROOT / "aromagen" / "data" / "dialogue" / "compose.txt"
CSV_OUT_PATH = ROOT / "theme_taxonomy.csv"
CHART_OUT_PATH = ROOT / "theme_pie_chart.png"
DEDUP_NOTE_PATH = ROOT / "dedup_note.txt"

# Keyword buckets pulled from words actually seen across the dialogue logs
# (word cloud + manual noise-audit review), not guessed generically.
THEME_KEYWORDS = {
    "food": [
        "garlic", "cilantro", "mango", "citrus", "coffee", "satay", "chicken",
        "lemongrass", "ginger", "fish", "seafood", "mcdonald", "fries", "big mac",
        "dessert", "hawker", "taco", "yakiniku", "cocktail", "spice", "cumin",
        "sweet potato", "lobster", "ramen", "croissant", "pastries", "bread",
        "chocolate", "candy", "sugar", "food", "meal", "lunch", "breakfast",
        "restaurant", "curry", "tangerine", "bbq", "barbecue",
    ],
    "nature": [
        "flower", "lavender", "forest", "tree", "plant", "garden", "botanic",
        "rain", "sea", "seaside", "ocean", "wave", "animal", "zoo", "safari",
        "tiger", "lion", "orchid", "citronelly", "eucalipto", "mugwort",
        "spearmint", "grass", "wind", "sunny", "humid", "sunset",
    ],
    "place": [
        "singapore", "marina bay", "city", "new york", "paris", "chinatown",
        "airport", "museum", "edinburgh", "tokyo", "orchard road", "botanical",
        "hawker center", "beach", "street", "room", "cafe", "shop",
    ],
    "memory": [
        "remember", "memory", "childhood", "grandma", "grandmother", "nostalgia",
        "family", "friend", "sister", "wife", "husband", "birth", "exchange program",
        "playing outside", "growing up",
    ],
}

# Same filler list built while tuning the word cloud stopwords.
FILLER_WORDS = {
    "um", "uh", "like", "yeah", "so", "okay", "well", "really", "actually",
    "know", "think", "something", "kind", "going", "just", "very",
}

FILLER_RATIO_THRESHOLD = 0.25

# Lines already manually confirmed as noise during the earlier review
# (off-topic project conversation, garbled Whisper transcript).
MANUAL_NOISE_SUBSTRINGS = [
    "media lab",
    "translate your sentence",
]

# Corrections from manual review of theme_taxonomy.csv. Each entry is a
# distinctive lowercase substring matched against a line, mapped to the
# category the manual review determined is correct. Applied after the
# automatic rules, since these are holistic-reading calls (or true
# incoherence) that the keyword/pattern rules can't reliably generalize.
MANUAL_OVERRIDES = [
    ("smell of the sunset", "nature"),
    ("lavender. lavender", "nature"),
    ("i am running forward", "noise"),
    ("abstract, emotional", "memory"),
    ("is it enough", "place"),
    ("curry all over my fingers", "memory"),
    ("let's do maybe barbecue", "noise"),
    ("sadness?", "other"),
    ("warm clove around me", "memory"),
    ("exploring the nature and the new technology", "memory"),
    ("night zoo here in singapore", "place"),
    ("joe malone orange blossom", "nature"),
    ("hawker markets", "place"),
    ("spring court", "place"),
    ("hell museum place", "place"),
    ("every time you give it feedback", "noise"),
    ("does that work", "memory"),
    ("chocolate croissant", "food"),
    ("water bomb", "memory"),
    ("mexican taco", "food"),
    ("friend of the pastor", "other"),
    ("tanjung pagar", "place"),
    ("floating fish, peace in the cloud", "nature"),
    ("the scent of fresh fruit", "food"),
    ("golden treat resting in eager hands", "nature"),
    ("sun-kissed lemons", "nature"),
    ("freshly baked pastries", "memory"),
    ("chocolate mousse", "food"),
    # the passage describes both a specific setting and a
    # nostalgic/reflective mood equally strongly.
    ("polished wood and the faint mustiness", "place & memory"),
]


def has_repetition(text: str, window: int = 3) -> bool:
    words = text.lower().split()
    seen = set()
    for i in range(len(words) - window + 1):
        phrase = tuple(words[i : i + window])
        if phrase in seen:
            return True
        seen.add(phrase)
    return False


def filler_ratio(text: str) -> float:
    words = text.lower().split()
    if not words:
        return 0.0
    filler_count = sum(1 for w in words if w.strip(".,!?'\"") in FILLER_WORDS)
    return filler_count / len(words)


def is_facilitator_question(text: str) -> bool:
    lowered = text.lower()
    has_question = "?" in text
    is_second_person = any(p in lowered for p in ("you ", "your ", "you're", "you'd"))
    return has_question and is_second_person


def classify_theme(text: str) -> tuple[str, int]:
    lowered = text.lower()
    scores = {theme: 0 for theme in THEME_KEYWORDS}
    for theme, keywords in THEME_KEYWORDS.items():
        for kw in keywords:
            if kw in lowered:
                scores[theme] += 1
    best_theme = max(scores, key=lambda t: scores[t])
    best_score = scores[best_theme]
    if best_score == 0:
        return "other", 0
    return best_theme, best_score


def classify_line(text: str) -> tuple[str, str]:
    """Returns (category, reason). category is one of the 5 themes or 'noise'."""
    stripped = text.strip()
    lowered = stripped.lower()

    for substring, category in MANUAL_OVERRIDES:
        if substring in lowered:
            return category, "manual_override"

    if any(sub in lowered for sub in MANUAL_NOISE_SUBSTRINGS):
        return "noise", "manual_exclude_list"

    word_count = len(stripped.split())

    if word_count == 1:
        theme, score = classify_theme(stripped)
        if score == 0:
            return "noise", "single_word_no_theme_match"
        return theme, f"single_word_matched_{theme}"

    if is_facilitator_question(stripped):
        return "noise", "facilitator_question_pattern"

    if has_repetition(stripped):
        return "noise", "repeated_phrase_candidate"

    ratio = filler_ratio(stripped)
    if ratio > FILLER_RATIO_THRESHOLD:
        return "noise", f"high_filler_ratio_{ratio:.2f}"

    theme, score = classify_theme(stripped)
    return theme, f"keyword_match_score_{score}"


def main() -> None:
    sessions = []
    for line in INPUT_PATH.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        data = json.loads(line)
        sessions.append(
            {
                "session_id": data.get("session_id"),
                "timestamp": data.get("timestamp"),
                "text": (data.get("human_input") or "").strip(),
            }
        )

    # Sanity check: session_id should be unique per row - if any repeat, that
    # WOULD be a true logging duplicate (unlike the earlier, incorrect
    # text-based dedup, which discarded 5 real distinct sessions that just
    # happened to produce identical text/output - see dedup_note.txt).
    session_id_counts = Counter(s["session_id"] for s in sessions)
    true_duplicates = {sid: count for sid, count in session_id_counts.items() if count > 1}

    text_counts = Counter(s["text"] for s in sessions)
    coincidental_matches = {text: count for text, count in text_counts.items() if count > 1}

    note_lines = [
        "Correction (2026-07-10): the earlier version of this script deduplicated",
        "by exact text match, which incorrectly treated 5 pairs of DIFFERENT",
        "sessions (different session_id) as duplicates and discarded one from",
        "each pair. All 99 compose sessions have unique session_id values - none",
        "are true logging duplicates. The pairs below share identical text/output",
        "by coincidence (or a system behavior worth investigating separately),",
        "not because of a data error, and are now both kept:",
        "",
    ]
    for text, count in coincidental_matches.items():
        note_lines.append(f"  x{count}: {text[:100]}{'...' if len(text) > 100 else ''}")
    if true_duplicates:
        note_lines.append("")
        note_lines.append("True session_id duplicates found (real logging issue):")
        for sid, count in true_duplicates.items():
            note_lines.append(f"  x{count}: {sid}")
    note_text = "\n".join(note_lines)
    print(note_text)
    DEDUP_NOTE_PATH.write_text(note_text + "\n", encoding="utf-8")

    rows = []
    theme_counts = Counter()
    for session in sessions:
        category, reason = classify_line(session["text"])
        rows.append(
            {
                "session_id": session["session_id"],
                "text": session["text"],
                "category": category,
                "reason": reason,
            }
        )
        if category != "noise":
            theme_counts[category] += 1

    with open(CSV_OUT_PATH, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["session_id", "text", "category", "reason"])
        writer.writeheader()
        writer.writerows(rows)

    noise_count = sum(1 for r in rows if r["category"] == "noise")
    print(f"Total lines: {len(rows)}")
    print(f"Flagged as noise: {noise_count}")
    print(f"Theme counts: {dict(theme_counts)}")
    print(f"Full breakdown written to {CSV_OUT_PATH}")

    labels = list(theme_counts.keys())
    sizes = [theme_counts[l] for l in labels]

    plt.figure(figsize=(7, 7))
    plt.pie(sizes, labels=labels, autopct="%1.1f%%")
    plt.title("First-compose themes (noise excluded)")
    plt.tight_layout(pad=0)
    plt.savefig(CHART_OUT_PATH, dpi=300, bbox_inches="tight")
    plt.show()


if __name__ == "__main__":
    main()
