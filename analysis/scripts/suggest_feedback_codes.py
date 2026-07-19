import csv
from pathlib import Path

ROOT = Path(__file__).resolve().parent
CSV_PATH = ROOT.parent / "outputs" / "feedback_coding" / "feedback_coding.csv"


CODE_KEYWORDS = {
    "sweeter": ["sweet"],
    "sour": ["sour"],
    "more spicy": ["spicy", "spicier", "spice"],
    "floral": ["floral", "lavender", "lilac", "lily"],
    "smoky": ["smoky", "smoking", "smoke"],
}


def suggest(text: str) -> str:
    if not text:
        return ""
    lowered = text.lower()
    matches = [code for code, keywords in CODE_KEYWORDS.items() if any(kw in lowered for kw in keywords)]
    return ", ".join(matches)


with open(CSV_PATH, "r", encoding="utf-8") as f:
    reader = csv.DictReader(f)
    rows = list(reader)
    fieldnames = reader.fieldnames + ["suggested_code"] if "suggested_code" not in reader.fieldnames else reader.fieldnames

filled = 0
for row in rows:
    if row.get("code", "").strip():
        row["suggested_code"] = ""  # already coded by hand, nothing to suggest
        continue
    suggestion = suggest(row.get("feedback_text", ""))
    row["suggested_code"] = suggestion
    if suggestion:
        filled += 1

with open(CSV_PATH, "w", newline="", encoding="utf-8") as f:
    writer = csv.DictWriter(f, fieldnames=fieldnames)
    writer.writeheader()
    writer.writerows(rows)

blank_rows = sum(1 for r in rows if not r.get("code", "").strip())
print(f"Blank (uncoded) rows: {blank_rows}")
print(f"Of those, keyword suggestions found for: {filled}")
print(f"Still with no suggestion at all: {blank_rows - filled}")
