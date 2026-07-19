# Demo Corpus Analysis (June 3–17, 2026)

Exploratory analysis of the June demo/exhibition dialogue logs: word cloud, theme classification, noise audit, scent usage, session funnel, feedback coding, and a theme-vs-acceptance-rate cross-reference. Built to characterize the corpus ahead of the July user study and to inform data selection for future fine-tuning work.

**Full write-up with findings and interpretation:** [`progress_summary.txt`](progress_summary.txt)

## Layout

```
analysis/
├── scripts/    # All analysis scripts, flat
└── outputs/    # Generated data + charts, one subfolder per analysis type
    ├── word_cloud/
    ├── theme_taxonomy/
    ├── scent_usage/
    ├── session_funnel/
    ├── theme_acceptance_rate/
    └── feedback_coding/
```

---

## Reproducing the analysis

Scripts read `aromagen/data/dialogue/` two levels up and write into their matching `outputs/<type>/` folder, so run them **from the repo root** (a Python venv with `matplotlib`, `wordcloud`, and `python-pptx` installed — see `requirements.txt`... these three aren't in it yet, install separately: `pip install matplotlib wordcloud python-pptx`).

### 1. Extract compose events from the raw logs (manual step, not yet scripted)

```bash
cd aromagen/data/dialogue
grep -h '"event": "compose"' dialogue_*.jsonl > compose.txt
cd ../../..
```

This is currently a manual prerequisite, not wrapped in a script — worth automating into `extract.py` if this pipeline gets reused later.

### 2. Extract per-session text and scent usage

```bash
python analysis/scripts/extract.py
```

Produces `aromagen/data/dialogue/human_input.txt` (one sentence per session) and `analysis/outputs/scent_usage/scent_usage.csv` (one row per scent occurrence).

### 3. Word cloud

```bash
python analysis/scripts/word_cloud.py
```

Produces `analysis/outputs/word_cloud/wordcloud_filtered2.png`. (`wordcloud_unfiltered.png` / `wordcloud_filtered.png` are earlier iterations kept for reference, not final.)

### 4. Theme taxonomy + noise audit

```bash
python analysis/scripts/theme_taxonomy.py
```

Produces `theme_taxonomy.csv`, `theme_pie_chart.png`, `dedup_note.txt` (in `analysis/outputs/theme_taxonomy/`). Classification combines automatic rules with a hard-coded manual override table (33 entries, built from a full line-by-line review) — re-running this script reproduces the same result exactly, since the overrides are part of the script, not a separate manual edit step.

### 5. Scent usage

```bash
python analysis/scripts/scent_usage.py
```

Produces `scent_counts_bar.png`, `scent_by_day_bar.png` (in `analysis/outputs/scent_usage/`).

### 6. Session funnel

```bash
python analysis/scripts/session_funnel.py
```

Produces `session_funnel.csv`, `accept_iterations.csv`, `session_funnel_bar.png`, `accept_iterations_bar.png` (in `analysis/outputs/session_funnel/`).

### 7. Theme vs. acceptance rate

```bash
python analysis/scripts/theme_acceptance_rate.py
```

Requires steps 4 and 6 to have already run — reads `outputs/theme_taxonomy/theme_taxonomy.csv` and `outputs/session_funnel/accept_iterations.csv`, joined on `session_id`. Produces `theme_acceptance_rate.csv`, `theme_acceptance_rate_bar.png` (in `analysis/outputs/theme_acceptance_rate/`).

### 8. Feedback coding (qualitative — requires manual work, not fully automated)

```bash
python analysis/scripts/feedback_coding.py          # extracts all 85 feedback rounds to feedback_coding.csv, code column empty
python analysis/scripts/suggest_feedback_codes.py   # optional: adds keyword-based code suggestions to speed up manual review
# --- manual step: code the CSV by hand, review/confirm suggestions ---
python analysis/scripts/map_scent_quality.py        # maps hand-assigned codes onto the odor-quality taxonomy + direction
python analysis/scripts/feedback_quality_chart.py   # produces feedback_quality_bar.png
```

All of the above read/write `analysis/outputs/feedback_coding/feedback_coding.csv`. Note: re-running `feedback_coding.py` overwrites that file from scratch, including the `code`/`notes` columns from prior manual coding — don't re-run it once you've started coding by hand, or you'll lose that work.

The `code` column in `feedback_coding.csv` as currently committed reflects one researcher's manual pass — per the study protocol (section 14), this should get a second independent coder on a subset before being treated as final.

---

## Files produced

| Output folder | Produced by | Contents |
|---|---|---|
| `outputs/scent_usage/scent_usage.csv`, `aromagen/data/dialogue/human_input.txt` | `scripts/extract.py` | Per-session text and scent occurrences |
| `outputs/word_cloud/wordcloud_filtered2.png` | `scripts/word_cloud.py` | Word cloud of session inputs |
| `outputs/theme_taxonomy/theme_taxonomy.csv`, `theme_pie_chart.png` | `scripts/theme_taxonomy.py` | Theme classification + noise flags |
| `outputs/theme_taxonomy/dedup_note.txt` | `scripts/theme_taxonomy.py` | Documents a coincidental identical-text/output finding across 5 session pairs (not logging duplicates — see file for detail) |
| `outputs/scent_usage/scent_counts_bar.png`, `scent_by_day_bar.png` | `scripts/scent_usage.py` | Scent frequency + floral-bias analysis |
| `outputs/session_funnel/session_funnel.csv`, `accept_iterations.csv`, and both bar charts | `scripts/session_funnel.py` | Daily compose→feedback→accept funnel |
| `outputs/theme_acceptance_rate/theme_acceptance_rate.csv`, `theme_acceptance_rate_bar.png` | `scripts/theme_acceptance_rate.py` | Acceptance rate by theme |
| `outputs/feedback_coding/feedback_coding.csv`, `feedback_quality_bar.png` | `scripts/feedback_coding.py` + `map_scent_quality.py` + `feedback_quality_chart.py` | Qualitative feedback coding |
| `finetune_learning_guide.txt` | — | Self-paced reference for the next phase (`prepare_finetune.py` / `eval_models.py`), not committed to git (personal notes) |

---

## Key findings (summary — see `progress_summary.txt` for full detail)

- Theme breakdown (99 sessions): Nature 23, Food 20, Place 16, Memory 10, Other 8, Place & Memory 1, Noise 21 (excluded from theme %).
- Floral-default bias: 62.6% of sessions include at least one of the fixed default floral scents — the two most-used scents corpus-wide.
- Daily acceptance rate declines across the busiest days (12.8% → 10.5% → 5.9%), matching the study protocol's own documented finding.
- Memory-themed sessions accept far more often (50%) than any other theme — flagged as a candidate finding given small per-theme sample sizes.
- Sweet and Fragrant dominate genuine (non-noise) feedback-coding requests, consistent with the floral-bias finding above.

## Outstanding

- Feedback coding needs a second independent coder for inter-rater reliability (study protocol section 14).
- `prepare_finetune.py` / `eval_models.py`