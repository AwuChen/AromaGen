"""
Automated AI validation pipeline for AromaGen composition quality.

Covers the automatable parts of the validation plan:
  A. Consistency testing   -- repeat each target N times, measure how often
                               the same odorant set / dominant odorant recurs.
  B. Edge-case evaluation  -- flag targets (esp. fruit_edge_cases) that
                               collapsed to a single odorant instead of a
                               reasonable multi-odorant blend.
  D. Automated batch query -- fire all ~100 targets x N repeats at the live
                               /compose endpoint, save every raw response,
                               and produce one CSV built for batch review.

Does NOT automate (left as blank columns in the review CSV for a human):
  C. Expert reasonableness -- "does this combination actually smell right"
     is a judgment call this script can't make. What it DOES do
     automatically is surface the system's own `compatibility_warnings`
     field (avoid_with violations) on every response, so a violation the
     system itself flagged doesn't get missed as your eye scans 100 rows.
  "Missing odorants" -- also left to human review; requires knowing what
     SHOULD have been included, which is a judgment call, not something
     inferable from the response alone.

Usage:
    python3 run_validation.py --smoke
        Tiny 3-target x 2-repeat sanity check that the pipeline + backend
        connection actually works, before spending real API budget on the
        full batch.

    python3 run_validation.py --repeats 5
        Full ~100-target x 5-repeat run (~500 /compose calls). Saves to
        results/<timestamp>/.

    python3 run_validation.py --repeats 5 --categories fruit_edge_cases,savory_cooked
        Restrict to specific categories from targets.py.

Requires the AI backend running locally (default http://localhost:8000) --
this hits the real /compose endpoint, which means real OpenAI API calls and
real cost/latency. Not a mock.
"""
from __future__ import annotations

import argparse
import csv
import json
import sys
import time
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

import requests

from targets import TARGETS, flatten_targets

DEFAULT_BASE_URL = "http://localhost:8000"
DEFAULT_REPEATS = 10
REQUEST_TIMEOUT_S = 60


def call_compose(base_url: str, sentence: str) -> Dict[str, Any]:
    resp = requests.post(
        f"{base_url}/compose",
        json={"sentence": sentence},
        timeout=REQUEST_TIMEOUT_S,
    )
    resp.raise_for_status()
    return resp.json()


def odorant_set(response: Dict[str, Any]) -> frozenset:
    """The conceptual odorant pick (pre-pulse-expansion), deduped by name.
    Uses `scent_sequence` (the model's own pick), not `pulse_sequence`
    (which repeats each name many times for hardware playback -- using
    that here would trivially always look "consistent" on set membership
    while hiding real differences in composition)."""
    return frozenset(item["scent_name"] for item in response.get("scent_sequence", []))


def dominant_odorant(response: Dict[str, Any]) -> Optional[str]:
    seq = response.get("scent_sequence", [])
    if not seq:
        return None
    return max(seq, key=lambda item: item.get("ratio", 0.0))["scent_name"]


def run_target(base_url: str, category: str, target: str, notes_hint: Optional[str], repeats: int) -> Dict[str, Any]:
    runs: List[Dict[str, Any]] = []
    for i in range(repeats):
        try:
            response = call_compose(base_url, target)
            runs.append({"run_index": i, "ok": True, "response": response})
        except Exception as e:
            runs.append({"run_index": i, "ok": False, "error": str(e)})
    return {"category": category, "target": target, "notes_hint": notes_hint, "runs": runs}


def summarize_target(record: Dict[str, Any]) -> Dict[str, Any]:
    ok_runs = [r["response"] for r in record["runs"] if r["ok"]]
    n_ok = len(ok_runs)
    n_total = len(record["runs"])

    sets = [odorant_set(r) for r in ok_runs]
    set_counts = Counter(sets)
    modal_set, modal_count = (set_counts.most_common(1)[0] if set_counts else (frozenset(), 0))
    set_stability = modal_count / n_ok if n_ok else 0.0

    dominants = [dominant_odorant(r) for r in ok_runs]
    dom_counts = Counter(dominants)
    modal_dom, modal_dom_count = (dom_counts.most_common(1)[0] if dom_counts else (None, 0))
    dominant_stability = modal_dom_count / n_ok if n_ok else 0.0

    single_odorant_runs = sum(1 for s in sets if len(s) == 1)
    single_odorant_majority = n_ok > 0 and single_odorant_runs > n_ok / 2

    compat_warnings = []
    for r in ok_runs:
        for w in r.get("compatibility_warnings", []) or []:
            if w not in compat_warnings:
                compat_warnings.append(w)

    sample_justification = ok_runs[0]["justification"] if ok_runs else ""

    return {
        "category": record["category"],
        "target": record["target"],
        "notes_hint": record["notes_hint"] or "",
        "n_ok": n_ok,
        "n_total": n_total,
        "modal_odorant_set": ", ".join(sorted(modal_set)),
        "set_stability": round(set_stability, 2),
        "modal_dominant_odorant": modal_dom or "",
        "dominant_stability": round(dominant_stability, 2),
        "single_odorant_majority_flag": single_odorant_majority,
        "compatibility_warnings": " | ".join(compat_warnings),
        "sample_justification": sample_justification,
        "expert_reasonable_yn": "",  # blank -- fill in during manual review
        "expert_notes": "",  # blank -- fill in during manual review
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--repeats", type=int, default=DEFAULT_REPEATS, help=f"Repeats per target (default {DEFAULT_REPEATS})")
    parser.add_argument("--base-url", default=DEFAULT_BASE_URL, help=f"AI backend base URL (default {DEFAULT_BASE_URL})")
    parser.add_argument("--categories", default=None, help="Comma-separated category filter (default: all)")
    parser.add_argument("--out", default=None, help="Output directory (default: results/<timestamp>)")
    parser.add_argument("--smoke", action="store_true", help="Tiny 3-target x 2-repeat sanity check instead of the full batch")
    args = parser.parse_args()

    try:
        health = requests.get(f"{args.base_url}/health", timeout=5)
        health.raise_for_status()
    except Exception as e:
        print(f"ERROR: backend not reachable at {args.base_url} ({e}). Start it before running this script.", file=sys.stderr)
        sys.exit(1)

    targets = list(flatten_targets())
    if args.categories:
        wanted = set(c.strip() for c in args.categories.split(","))
        targets = [t for t in targets if t[0] in wanted]

    repeats = args.repeats
    if args.smoke:
        targets = targets[:3]
        repeats = min(repeats, 2)
        print("SMOKE TEST: 3 targets x", repeats, "repeats")

    out_dir = Path(args.out) if args.out else Path("results") / datetime.now(timezone.utc).strftime("%Y-%m-%dT%H%M%SZ")
    out_dir.mkdir(parents=True, exist_ok=True)

    print(f"Running {len(targets)} targets x {repeats} repeats = {len(targets) * repeats} /compose calls against {args.base_url}")
    print(f"Output: {out_dir}")

    raw_records = []
    summaries = []
    t_start = time.time()
    for idx, (category, target, notes_hint) in enumerate(targets, 1):
        print(f"  [{idx}/{len(targets)}] {category}: {target!r}")
        record = run_target(args.base_url, category, target, notes_hint, repeats)
        raw_records.append(record)
        summaries.append(summarize_target(record))

    elapsed = time.time() - t_start
    print(f"Done in {elapsed:.1f}s")

    raw_path = out_dir / "raw_responses.json"
    raw_path.write_text(json.dumps(raw_records, indent=2, ensure_ascii=False), encoding="utf-8")

    csv_path = out_dir / "review.csv"
    fieldnames = [
        "category", "target", "notes_hint", "n_ok", "n_total",
        "modal_odorant_set", "set_stability", "modal_dominant_odorant", "dominant_stability",
        "single_odorant_majority_flag", "compatibility_warnings", "sample_justification",
        "expert_reasonable_yn", "expert_notes",
    ]
    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(summaries)

    # Console summary -- what to look at first, not a full report
    n = len(summaries)
    avg_set_stability = sum(s["set_stability"] for s in summaries) / n if n else 0
    avg_dom_stability = sum(s["dominant_stability"] for s in summaries) / n if n else 0
    low_stability = [s for s in summaries if s["set_stability"] < 0.6]
    single_odorant_flags = [s for s in summaries if s["single_odorant_majority_flag"]]
    compat_flags = [s for s in summaries if s["compatibility_warnings"]]
    failed_calls = [s for s in summaries if s["n_ok"] < s["n_total"]]

    print("\n=== Summary ===")
    print(f"Avg odorant-set stability across repeats: {avg_set_stability:.0%}")
    print(f"Avg dominant-odorant stability across repeats: {avg_dom_stability:.0%}")
    print(f"Targets with set_stability < 60% (n={len(low_stability)}): {[s['target'] for s in low_stability]}")
    print(f"Targets that collapsed to a single odorant in most runs (n={len(single_odorant_flags)}): {[s['target'] for s in single_odorant_flags]}")
    print(f"Targets with a compatibility_warnings hit (n={len(compat_flags)}): {[s['target'] for s in compat_flags]}")
    if failed_calls:
        print(f"Targets with failed/errored calls (n={len(failed_calls)}): {[(s['target'], s['n_ok'], s['n_total']) for s in failed_calls]}")

    print(f"\nRaw responses: {raw_path}")
    print(f"Review CSV:    {csv_path}")


if __name__ == "__main__":
    main()
