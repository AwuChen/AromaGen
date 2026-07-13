import csv
from collections import Counter
from pathlib import Path

import matplotlib.pyplot as plt

ROOT = Path(__file__).resolve().parent
THEME_CSV = ROOT / "theme_taxonomy.csv"
ACCEPT_CSV = ROOT / "accept_iterations.csv"
OUT_CSV = ROOT / "theme_acceptance_rate.csv"
CHART_PATH = ROOT / "theme_acceptance_rate_bar.png"

with open(THEME_CSV, "r", encoding="utf-8") as f:
    theme_rows = list(csv.DictReader(f))

with open(ACCEPT_CSV, "r", encoding="utf-8") as f:
    accepted_session_ids = {row["session_id"] for row in csv.DictReader(f)}

# Noise-flagged sessions don't have a meaningful theme to test acceptance
# against, so they're excluded here the same way they're excluded from the
# theme_taxonomy.py pie chart.
themed_rows = [r for r in theme_rows if r["category"] != "noise"]

total_by_theme = Counter(r["category"] for r in themed_rows)
accepted_by_theme = Counter(
    r["category"] for r in themed_rows if r["session_id"] in accepted_session_ids
)

results = []
for theme, total in total_by_theme.items():
    accepted = accepted_by_theme.get(theme, 0)
    rate = 100 * accepted / total if total else 0
    results.append({"theme": theme, "sessions": total, "accepted": accepted, "acceptance_rate_pct": round(rate, 1)})

results.sort(key=lambda r: -r["acceptance_rate_pct"])

with open(OUT_CSV, "w", newline="", encoding="utf-8") as f:
    writer = csv.DictWriter(f, fieldnames=["theme", "sessions", "accepted", "acceptance_rate_pct"])
    writer.writeheader()
    writer.writerows(results)

print("Theme vs. acceptance rate:")
for r in results:
    print(f"  {r['theme']}: {r['accepted']}/{r['sessions']} accepted ({r['acceptance_rate_pct']}%)")

labels = [r["theme"] for r in results]
rates = [r["acceptance_rate_pct"] for r in results]

plt.figure(figsize=(9, 5.5))
bars = plt.bar(labels, rates, color="#4C72B0")
plt.ylabel("Acceptance rate (%)")
plt.title("Acceptance rate by theme")
plt.bar_label(bars, padding=3, fmt="%.1f%%")
plt.tight_layout(pad=0.5)
plt.savefig(CHART_PATH, dpi=300, bbox_inches="tight")
plt.show()
