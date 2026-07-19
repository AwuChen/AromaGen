'''
1. read the scent_usage.csv file
2. collect the count of every scent_name across all rows into the counter
3. group rows by session_id: For each session, I want the set of scents used
(not a count, since duplicates within one session's scent_sequence are unlikely
 but worth guarding against) — a dict mapping session_id -> set of scent_names works,
  built by iterating rows and adding to dict.setdefault(session_id, set()).add(scent_name).
4. Per-day tally: you'll need to turn each timestamp (e.g. "2026-06-03T22:22:46.048895+00:00") into just a date.
The string's first 10 characters (timestamp[:10]) already give you "2026-06-03" without needing
 to parse it as a real datetime object — simplest option given the ISO format is fixed-width.
  Group scent occurrences by that date string, then Counter per day (total occurrences per day).

5. Floral-bias %: reuse the per-session sets from step 3 — for each session's set,
 check intersection with {"Citronelly", "Lavender", "Eucalipto"},
 count sessions with a non-empty intersection, divide by total sessions.
'''

import csv
from collections import Counter, defaultdict
from pathlib import Path

import matplotlib.pyplot as plt

ROOT = Path(__file__).resolve().parent
OUT_DIR = ROOT.parent / "outputs" / "scent_usage"
CSV_PATH = OUT_DIR / "scent_usage.csv"
SCENT_CHART_PATH = OUT_DIR / "scent_counts_bar.png"
DAILY_CHART_PATH = OUT_DIR / "scent_by_day_bar.png"

# Substring stems, not exact names: the catalog stores these as "Citronelly acet"
# and "Lavendar oil" (note the "Lavendar" spelling in the actual data), not the
# plain names from the study protocol doc. Matching by stem catches both.
FLORAL_STEMS = ["citronelly", "lavend", "eucalipto"]

with open(CSV_PATH, "r", encoding="utf-8") as f:
    reader = csv.DictReader(f)
    rows = list(reader)

scent_counter = Counter(row["scent_name"] for row in rows)

session_scent_sets = defaultdict(set)
for row in rows:
    session_scent_sets[row["session_id"]].add(row["scent_name"])

daily_counter = Counter(row["timestamp"][:10] for row in rows)

floral_sessions = 0
for session_id, scents in session_scent_sets.items():
    if any(stem in scent.lower() for scent in scents for stem in FLORAL_STEMS):
        floral_sessions += 1
total_sessions = len(session_scent_sets)
floral_pct = 100 * floral_sessions / total_sessions if total_sessions else 0

print("Scent counts across all sessions:", scent_counter)
print(f"Sessions with at least one floral scent: {floral_sessions}/{total_sessions} ({floral_pct:.1f}%)")
print("Scent occurrences by day:", dict(sorted(daily_counter.items())))

# Chart 1: most-used scents, corpus-wide
scents_sorted = scent_counter.most_common()
labels = [s for s, _ in scents_sorted]
counts = [c for _, c in scents_sorted]

plt.figure(figsize=(10, 6))
bars1 = plt.barh(labels, counts, color="#4C72B0")
plt.gca().invert_yaxis()  # highest count at the top
plt.xlabel("Occurrences across all sessions")
plt.title("Most-used scents (corpus-wide)")
plt.bar_label(bars1, padding=3)
plt.tight_layout(pad=0.5)
plt.savefig(SCENT_CHART_PATH, dpi=300, bbox_inches="tight")

# Chart 2: scent occurrences by day
days_sorted = sorted(daily_counter.items())
day_labels = [d for d, _ in days_sorted]
day_counts = [c for _, c in days_sorted]

plt.figure(figsize=(10, 5))
bars2 = plt.bar(day_labels, day_counts, color="#55A868")
plt.xlabel("Day")
plt.ylabel("Scent occurrences")
plt.title("Scent usage by day")
plt.xticks(rotation=45, ha="right")
plt.bar_label(bars2, padding=3)
plt.tight_layout(pad=0.5)
plt.savefig(DAILY_CHART_PATH, dpi=300, bbox_inches="tight")

plt.show()
