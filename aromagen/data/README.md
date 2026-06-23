# AromaGen — interaction corpus summary (demo deployments, Jun 2026)

This folder contains logged multimodal scent-composition sessions collected during demo and exhibition deployments.

## Files

| Path | Description |
|------|-------------|
| `dialogue/dialogue_YYYY-MM-DD.jsonl` | Raw event logs (one JSON object per line) |
| `learned_examples.json` | User-accepted compositions injected at compose time |
| `exports/training_*.jsonl` | Filtered training splits (regenerate with `python scripts/export_training_data.py`) |
| `exports/export_summary.json` | Row counts from last export |

## Event types (`dialogue/*.jsonl`)

| Event | Fields of interest |
|-------|-------------------|
| `transcribe` | `human_input` (Whisper transcript) |
| `compose` | `human_input`, `response.scent_sequence`, `response.justification` |
| `feedback` | `request.latest_feedback`, `response.changes_made`, revised sequence |
| `accept` | `request.original_sentence`, `request.final_sequence`, `request.feedback_rounds` |
| `describe_image` | image → sensory text → compose pipeline |

## Current corpus stats (Jun 3–17, 2026)

| Metric | Count |
|--------|------:|
| Log files | 7 |
| Total events | 371 |
| Unique sessions | 99 |
| Compose | 99 |
| Feedback rounds | 85 |
| Accepts | 11 |
| Ratings | 0 |

**Themes (first compose per session):** food 24%, nature 18%, place 12%, memory 8%, other 37%.

Session span (first→last event): median ~75s.

## Usage

### Regenerate training exports

```bash
python scripts/export_training_data.py
```

Outputs:
- `exports/training_compose.jsonl` — `(sentence → sequence)` pairs (inputs ≥20 chars)
- `exports/training_feedback.jsonl` — refinement trajectories
- `exports/training_accept.jsonl` — validated finals

### Append new sessions

New events are written automatically when `DIALOGUE_LOGGING=true` (default). Logs land in `dialogue/dialogue_<UTC-date>.jsonl`.

## Citation & release

Released with the AromaGen CHI submission. Demo sessions prior to IRB-approved user studies (July 2026) are included as exploratory interaction logs; formal study data will be added under the same schema with participant IDs.

## Privacy

Do not commit `.env` or API keys. Review dialogue logs before public release and redact identifying information if needed.
