import csv
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DIALOGUE_DIR = ROOT / "aromagen" / "data" / "dialogue"
OUT_PATH = ROOT / "feedback_coding.csv"


def load_events():
    for path in sorted(DIALOGUE_DIR.glob("dialogue_*.jsonl")):
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line:
                yield json.loads(line)


rows = []
for event in load_events():
    if event.get("event") != "feedback":
        continue
    req = event.get("request", {})
    rows.append(
        {
            "session_id": event.get("session_id"),
            "day": (event.get("timestamp") or "")[:10],
            "original_sentence": req.get("original_sentence"),
            "feedback_text": req.get("latest_feedback"),
            "changes_made": event.get("response", {}).get("changes_made"),
            "code": "",
            "notes": "",
        }
    )

with open(OUT_PATH, "w", newline="", encoding="utf-8") as f:
    writer = csv.DictWriter(
        f, fieldnames=["session_id", "day", "original_sentence", "feedback_text", "changes_made", "code", "notes"]
    )
    writer.writeheader()
    writer.writerows(rows)

print(f"Extracted {len(rows)} feedback rounds to {OUT_PATH}")
