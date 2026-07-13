# Demo Corpus Analysis (June 3–17, 2026)

Exploratory analysis of the June demo/exhibition dialogue logs: word cloud, theme classification, noise audit, scent usage, session funnel, feedback coding, and a theme-vs-acceptance-rate cross-reference. Built to characterize the corpus ahead of the July IRB-approved study and to inform data selection for future fine-tuning work.

**Full write-up with findings and interpretation:** [`progress_summary.txt`](progress_summary.txt)
**Slide deck:** [`AromaGen_Findings_Presentation.pptx`](AromaGen_Findings_Presentation.pptx)

---

## Reproducing the analysis

Run in this order from the repo root (a Python venv with `matplotlib`, `wordcloud`, and `python-pptx` installed — see `requirements.txt`... these three aren't in it yet, install separately: `pip install matplotlib wordcloud python-pptx`).

### 1. Extract compose events from the raw logs (manual step, not yet scripted)

```bash
cd aromagen/data/dialogue
grep -h '"event": "compose"' dialogue_*.jsonl > compose.txt
cd ../../..
```

This is currently a manual prerequisite, not wrapped in a script — worth automating into `extract.py` if this pipeline gets reused later.

### 2. Extract per-session text and scent usage

```bash
python extract.py
```

Produces `aromagen/data/dialogue/human_input.txt` (one sentence per session) and `scent_usage.csv` (one row per scent occurrence).

### 3. Word cloud

```bash
python word_cloud.py
```

Produces `wordcloud_filtered2.png`. (`wordcloud_unfiltered.png` / `wordcloud_filtered.png` are earlier iterations kept for reference, not final.)

### 4. Theme taxonomy + noise audit

```bash
python theme_taxonomy.py
```

Produces `theme_taxonomy.csv`, `theme_pie_chart.png`, `dedup_note.txt`. Classification combines automatic rules with a hard-coded manual override table (33 entries, built from a full line-by-line review) — re-running this script reproduces the same result exactly, since the overrides are part of the script, not a separate manual edit step.

### 5. Scent usage

```bash
python scent_usage.py
```

Produces `scent_counts_bar.png`, `scent_by_day_bar.png`.

### 6. Session funnel

```bash
python session_funnel.py
```

Produces `session_funnel.csv`, `accept_iterations.csv`, `session_funnel_bar.png`, `accept_iterations_bar.png`.

### 7. Theme vs. acceptance rate

```bash
python theme_acceptance_rate.py
```

Requires steps 4 and 6 to have already run (joins `theme_taxonomy.csv` with `accept_iterations.csv` on `session_id`). Produces `theme_acceptance_rate.csv`, `theme_acceptance_rate_bar.png`.

### 8. Feedback coding (qualitative — requires manual work, not fully automated)

```bash
python feedback_coding.py          # extracts all 85 feedback rounds to feedback_coding.csv, code column empty
python suggest_feedback_codes.py   # optional: adds keyword-based code suggestions to speed up manual review
# --- manual step: code the CSV by hand, review/confirm suggestions ---
python map_scent_quality.py        # maps hand-assigned codes onto the odor-quality taxonomy + direction
python feedback_quality_chart.py   # produces feedback_quality_bar.png
```

The `code` column in `feedback_coding.csv` as currently committed reflects one researcher's manual pass — per the study protocol (section 14), this should get a second independent coder on a subset before being treated as final.

---

## Files produced

| File | Produced by | Contents |
|---|---|---|
| `human_input.txt`, `scent_usage.csv` | `extract.py` | Per-session text and scent occurrences |
| `wordcloud_filtered2.png` | `word_cloud.py` | Word cloud of session inputs |
| `theme_taxonomy.csv`, `theme_pie_chart.png` | `theme_taxonomy.py` | Theme classification + noise flags |
| `dedup_note.txt` | `theme_taxonomy.py` | Documents a coincidental identical-text/output finding across 5 session pairs (not logging duplicates — see file for detail) |
| `scent_counts_bar.png`, `scent_by_day_bar.png` | `scent_usage.py` | Scent frequency + floral-bias analysis |
| `session_funnel.csv`, `accept_iterations.csv`, `session_funnel_bar.png`, `accept_iterations_bar.png` | `session_funnel.py` | Daily compose→feedback→accept funnel |
| `theme_acceptance_rate.csv`, `theme_acceptance_rate_bar.png` | `theme_acceptance_rate.py` | Acceptance rate by theme |
| `feedback_coding.csv`, `feedback_quality_bar.png` | `feedback_coding.py` + `map_scent_quality.py` + `feedback_quality_chart.py` | Qualitative feedback coding |
| `AromaGen_Findings_Presentation.pptx` | (hand-built from the above) | Slide deck for supervisor review |
| `finetune_learning_guide.txt` | — | Self-paced reference for the next phase (`prepare_finetune.py` / `eval_models.py`) |

---

## Key findings (summary — see `progress_summary.txt` for full detail)

- Theme breakdown (99 sessions): Nature 23, Food 20, Place 16, Memory 10, Other 8, Place & Memory 1, Noise 21 (excluded from theme %).
- Floral-default bias: 62.6% of sessions include at least one of the fixed default floral scents — the two most-used scents corpus-wide.
- Daily acceptance rate declines across the busiest days (12.8% → 10.5% → 5.9%), matching the study protocol's own documented finding.
- Memory-themed sessions accept far more often (50%) than any other theme — flagged as a candidate finding given small per-theme sample sizes.
- Sweet and Fragrant dominate genuine (non-noise) feedback-coding requests, consistent with the floral-bias finding above.

## Outstanding

- Feedback coding needs a second independent coder for inter-rater reliability (study protocol section 14).
- `prepare_finetune.py` / `eval_models.py` — IRB/consent cleared; still blocked on an OpenAI API key with fine-tuning access.
