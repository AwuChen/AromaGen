#!/usr/bin/env python3
"""Export compose / feedback / accept events from dialogue logs to JSONL training files."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DIALOGUE_DIR = ROOT / "aromagen" / "data" / "dialogue"
OUT_DIR = ROOT / "aromagen" / "data" / "exports"
MIN_INPUT_LEN = 20


def load_events():
    for path in sorted(DIALOGUE_DIR.glob("dialogue_*.jsonl")):
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line:
                yield json.loads(line)


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    compose_rows = []
    feedback_rows = []
    accept_rows = []
    stats = {"events": 0, "skipped_short_compose": 0}

    for event in load_events():
        stats["events"] += 1
        kind = event.get("event")
        if kind == "compose":
            text = event.get("human_input", "")
            if len(text.strip()) < MIN_INPUT_LEN:
                stats["skipped_short_compose"] += 1
                continue
            compose_rows.append(
                {
                    "sentence": text,
                    "scent_sequence": event.get("response", {}).get("scent_sequence", []),
                    "justification": event.get("response", {}).get("justification", ""),
                    "session_id": event.get("session_id") or event.get("response", {}).get("session_id"),
                    "timestamp": event.get("timestamp"),
                }
            )
        elif kind == "feedback":
            req = event.get("request", {})
            resp = event.get("response", {})
            feedback_rows.append(
                {
                    "original_sentence": req.get("original_sentence"),
                    "original_sequence": req.get("original_sequence"),
                    "prior_rounds": req.get("prior_rounds", []),
                    "feedback_text": req.get("latest_feedback"),
                    "resulting_sequence": resp.get("scent_sequence", []),
                    "changes_made": resp.get("changes_made", ""),
                    "session_id": req.get("session_id"),
                    "timestamp": event.get("timestamp"),
                }
            )
        elif kind == "accept":
            req = event.get("request", {})
            accept_rows.append(
                {
                    "sentence": req.get("original_sentence"),
                    "final_sequence": req.get("final_sequence", []),
                    "feedback_rounds": req.get("feedback_rounds", []),
                    "rating": req.get("rating"),
                    "session_id": req.get("session_id"),
                    "timestamp": event.get("timestamp"),
                }
            )

    def write_jsonl(name: str, rows: list) -> None:
        path = OUT_DIR / name
        with path.open("w", encoding="utf-8") as f:
            for row in rows:
                f.write(json.dumps(row, ensure_ascii=False) + "\n")
        print(f"  {path} ({len(rows)} rows)")

    print("Exporting training data from dialogue logs...")
    write_jsonl("training_compose.jsonl", compose_rows)
    write_jsonl("training_feedback.jsonl", feedback_rows)
    write_jsonl("training_accept.jsonl", accept_rows)

    summary = {
        "total_events": stats["events"],
        "compose": len(compose_rows),
        "feedback": len(feedback_rows),
        "accept": len(accept_rows),
        "skipped_short_compose": stats["skipped_short_compose"],
    }
    (OUT_DIR / "export_summary.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
