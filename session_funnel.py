import csv
import json
from collections import Counter
from pathlib import Path

import matplotlib.pyplot as plt

ROOT = Path(__file__).resolve().parent
DIALOGUE_DIR = ROOT / "aromagen" / "data" / "dialogue"

FUNNEL_CSV_PATH = ROOT / "session_funnel.csv"
ITERATIONS_CSV_PATH = ROOT / "accept_iterations.csv"
FUNNEL_CHART_PATH = ROOT / "session_funnel_bar.png"
ITERATIONS_CHART_PATH = ROOT / "accept_iterations_bar.png"


def load_events():
    for path in sorted(DIALOGUE_DIR.glob("dialogue_*.jsonl")):
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line:
                yield json.loads(line)


composes_by_day = Counter()
feedback_by_day = Counter()
accepts_by_day = Counter()

accept_rows = []  # session_id, day, iterations_before_accept

for event in load_events():
    kind = event.get("event")
    session_id = event.get("session_id")
    day = (event.get("timestamp") or "")[:10]

    if kind == "compose":
        composes_by_day[day] += 1

    elif kind == "feedback":
        feedback_by_day[day] += 1

    elif kind == "accept":
        accepts_by_day[day] += 1
        feedback_rounds = event.get("request", {}).get("feedback_rounds", [])
        accept_rows.append(
            {
                "session_id": session_id,
                "day": day,
                "iterations_before_accept": len(feedback_rounds),
            }
        )

all_days = sorted(set(composes_by_day) | set(feedback_by_day) | set(accepts_by_day))

funnel_rows = []
for day in all_days:
    composes = composes_by_day[day]
    accepts = accepts_by_day[day]
    rate = 100 * accepts / composes if composes else 0
    funnel_rows.append(
        {
            "day": day,
            "composes": composes,
            "feedback_rounds": feedback_by_day[day],
            "accepts": accepts,
            "acceptance_rate_pct": round(rate, 1),
        }
    )

with open(FUNNEL_CSV_PATH, "w", newline="", encoding="utf-8") as f:
    writer = csv.DictWriter(f, fieldnames=["day", "composes", "feedback_rounds", "accepts", "acceptance_rate_pct"])
    writer.writeheader()
    writer.writerows(funnel_rows)

with open(ITERATIONS_CSV_PATH, "w", newline="", encoding="utf-8") as f:
    writer = csv.DictWriter(f, fieldnames=["session_id", "day", "iterations_before_accept"])
    writer.writeheader()
    writer.writerows(accept_rows)

iteration_counts = Counter(r["iterations_before_accept"] for r in accept_rows)
first_try = iteration_counts.get(0, 0)
total_accepts = len(accept_rows)

print("Daily funnel (compose -> feedback -> accept):")
for row in funnel_rows:
    print(f"  {row['day']}: composes={row['composes']}, feedback_rounds={row['feedback_rounds']}, "
          f"accepts={row['accepts']}, acceptance_rate={row['acceptance_rate_pct']}%")
print(f"\nTotal accepts: {total_accepts}")
print(f"Accepted on first try (0 feedback rounds): {first_try}/{total_accepts}")
print(f"Iterations-before-accept distribution: {dict(sorted(iteration_counts.items()))}")

# Chart 1: daily funnel, composes vs feedback vs accepts, grouped bars
days = [r["day"] for r in funnel_rows]
composes_vals = [r["composes"] for r in funnel_rows]
feedback_vals = [r["feedback_rounds"] for r in funnel_rows]
accepts_vals = [r["accepts"] for r in funnel_rows]

x = range(len(days))
width = 0.25

plt.figure(figsize=(11, 6))
b1 = plt.bar([i - width for i in x], composes_vals, width, label="Composes", color="#4C72B0")
b2 = plt.bar(list(x), feedback_vals, width, label="Feedback rounds", color="#DD8452")
b3 = plt.bar([i + width for i in x], accepts_vals, width, label="Accepts", color="#55A868")
plt.xticks(list(x), days, rotation=45, ha="right")
plt.ylabel("Count")
plt.title("Daily funnel: compose -> feedback -> accept")
plt.legend()
plt.bar_label(b1, padding=2, fontsize=8)
plt.bar_label(b2, padding=2, fontsize=8)
plt.bar_label(b3, padding=2, fontsize=8)
plt.tight_layout(pad=0.5)
plt.savefig(FUNNEL_CHART_PATH, dpi=300, bbox_inches="tight")

# Chart 2: distribution of iterations before acceptance
iter_labels = sorted(iteration_counts.keys())
iter_counts = [iteration_counts[i] for i in iter_labels]
#O OR 1 is round 
# >1 is rounds
#A if cond1 else (B if cond2 else C)
iter_display_labels = ["First try (0)" if i == 0 else (f"{i} round" if i == 1 else f"{i} rounds") for i in iter_labels]

plt.figure(figsize=(8, 5))
b4 = plt.bar(iter_display_labels, iter_counts, color="#8172B2")
plt.ylabel("Number of accepted sessions")
plt.title("Feedback rounds before acceptance")
plt.bar_label(b4, padding=2)
plt.tight_layout(pad=0.5)
plt.savefig(ITERATIONS_CHART_PATH, dpi=300, bbox_inches="tight")

plt.show()
