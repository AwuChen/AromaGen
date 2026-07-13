import csv
from pathlib import Path

ROOT = Path(__file__).resolve().parent
CSV_PATH = ROOT / "feedback_coding.csv"

# Static odor-quality mapping, from the researcher's own scent guide, plus
# "Spicy" added as an 11th category - the guide has no clean bucket for
# food-spice feedback ("more spicy", "touch of pepper"), and it's common
# enough in this corpus (food is the largest theme) to warrant its own tag
# rather than being forced into "Pungent".
# Sour maps to Citrus, not Decayed - checked against context (paired with
# "citrus"/"fruity" in the source feedback), it consistently means
# tartness here, not spoilage, despite the guide's own "sour milk" example.
QUALITY_MAP = {
    "floral": "Fragrant",
    "citrus": "Citrus",
    "woody": "Woody and resinous",
    "earthy": "Woody and resinous",
    "fresh": "Woody and resinous",
    "sweeter": "Sweet",
    "sweet": "Sweet",
    "fruity": "Fruity",
    "decayed": "Decayed",
    "spicy/pungent": "Pungent",
    "smoky": "Pungent",
    "sour": "Citrus",
    "spicy": "Spicy",
    # Not in the published guide, and only 1 occurrence so far - logged as
    # its own tag rather than forced into an unrelated category, but kept
    # visually distinct since it isn't a validated category like "Spicy".
    "salty": "Salty (unvalidated)",
}

NON_SCENT_CODES = {"wrong catridge", "wrong cartridge"}

DIRECTION_PREFIXES = {"more": "increase", "less": "decrease"}


def strip_direction(tag: str) -> tuple[str, str]:
    lowered = tag.strip().lower()
    for prefix, direction in DIRECTION_PREFIXES.items():
        if lowered.startswith(prefix + " "):
            return lowered[len(prefix) + 1 :], direction
    return lowered, ""


with open(CSV_PATH, "r", encoding="utf-8") as f:
    reader = csv.DictReader(f)
    rows = list(reader)
    fieldnames = list(reader.fieldnames)

for col in ("scent_quality", "direction", "needs_review"):
    if col not in fieldnames:
        fieldnames.append(col)

flagged = 0
untouched = 0
for row in rows:
    code = row.get("code", "").strip()
    if not code:
        if "noise" in row.get("notes", "").lower():
            row["scent_quality"] = "Noise"
        else:
            row["scent_quality"] = ""
            untouched += 1
        row["direction"] = ""
        row["needs_review"] = ""
        continue

    tags = [t.strip() for t in code.split(",") if t.strip()]
    qualities = []
    directions = []
    unmapped = []

    for tag in tags:
        lowered = tag.lower()
        if lowered in NON_SCENT_CODES:
            qualities.append("Non-scent (technical/hardware)")
            continue

        base, direction = strip_direction(tag)
        if direction:
            directions.append(direction)

        lookup = lowered if lowered in QUALITY_MAP else base
        if lookup in QUALITY_MAP:
            qualities.append(QUALITY_MAP[lookup])
        else:
            unmapped.append(tag)

    row["scent_quality"] = ", ".join(dict.fromkeys(qualities))  # dedupe, keep order
    row["direction"] = ", ".join(dict.fromkeys(directions))
    row["needs_review"] = ", ".join(unmapped)
    if unmapped:
        flagged += 1

with open(CSV_PATH, "w", newline="", encoding="utf-8") as f:
    writer = csv.DictWriter(f, fieldnames=fieldnames)
    writer.writeheader()
    writer.writerows(rows)

print(f"Rows with a code: {sum(1 for r in rows if r.get('code','').strip())}")
print(f"Rows flagged noise (no code): {sum(1 for r in rows if 'noise' in r.get('notes','').lower() and not r.get('code','').strip())}")
print(f"Rows needing manual review (ambiguous / direction-only / unmapped): {flagged}")
print(f"Rows with neither a code nor a noise flag (still fully unaddressed): {untouched}")
