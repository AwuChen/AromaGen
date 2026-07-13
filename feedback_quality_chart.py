import csv
from collections import Counter
from pathlib import Path

import matplotlib.pyplot as plt

ROOT = Path(__file__).resolve().parent
CSV_PATH = ROOT / "feedback_coding.csv"
CHART_PATH = ROOT / "feedback_quality_bar.png"

with open(CSV_PATH, "r", encoding="utf-8") as f:
    rows = list(csv.DictReader(f))

quality_counts = Counter()
for row in rows:
    for q in row.get("scent_quality", "").split(","):
        q = q.strip()
        if q:
            quality_counts[q] += 1

sorted_items = quality_counts.most_common()
labels = [q for q, _ in sorted_items]
counts = [c for _, c in sorted_items]

plt.figure(figsize=(9, 5.5))
bars = plt.barh(labels, counts, color="#C44E52")
plt.gca().invert_yaxis()
plt.xlabel("Number of feedback rounds")
plt.title("Feedback coding: scent qualities requested")
plt.bar_label(bars, padding=3)
plt.tight_layout(pad=0.5)
plt.savefig(CHART_PATH, dpi=300, bbox_inches="tight")
plt.show()

coded = sum(1 for r in rows if r.get("code", "").strip())
print(f"Coded rows: {coded}/{len(rows)}")
print(f"Quality counts: {sorted_items}")
