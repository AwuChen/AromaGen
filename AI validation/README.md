# AI Validation

Automated + human-in-the-loop validation of AromaGen's composition quality,
covering the four areas from the validation plan:

- **A. Consistency testing** -- automated. `run_validation.py` calls
  `/compose` `--repeats` times per target and measures how often the same
  odorant set (and same dominant odorant) recurs.
- **B. Edge-case evaluation** -- automated flag, human judgment on the
  result. The script flags any target that collapsed to a single odorant in
  most runs (`single_odorant_majority_flag`) -- worth a look, but not
  automatically wrong (a single odorant can be the right call). Several of
  the 50 descriptors below (e.g. "guava", "currant") have no direct 1:1
  catalog odorant, so they double as edge cases even without a separate
  category for it.
- **C. Expert reasonableness check** -- NOT automated (this is a smell
  judgment call, not something this script can grade), except that every
  response's own `compatibility_warnings` field (the system's live
  `avoid_with` check) is surfaced in the CSV so a self-flagged violation
  doesn't get missed while scanning 100 rows. Fill in `expert_reasonable_yn`
  / `expert_notes` yourself in `review.csv`.
- **D. Automated batch evaluation** -- `run_validation.py` end-to-end:
  fires all targets x repeats at the live backend, saves every raw response,
  and writes one CSV built for scanning in a spreadsheet instead of
  re-querying the system by hand.

## Files

- `targets.py` -- the 50-descriptor / 12-cluster target list, identical to
  the taxonomy used in the human perception study (`Floral`, `Citrus`,
  `Woody & Resinous`, `Herbal & Cooling`, `Spice`, `Sweet & Gourmand`,
  `Roasted & Smoky`, `Fermented & Sour`, `Putrid & Decay`, `Body &
  Animalic`, `Chemical & Solvent`, `Perfumed & Clean`) -- same cluster
  names, same descriptor spellings, so results here are directly joinable
  against the human-study accuracy data by descriptor string. Also carries
  each descriptor's pleasantness/valence score where the source data
  provided one (`PLEASANTNESS` dict; not used by the script, reference
  only). Plain data, edit freely. Run `python3 targets.py` to print cluster
  counts.
- `run_validation.py` -- the pipeline. See `--help` or the module docstring
  for full usage.
- `results/<timestamp>/` -- one folder per run:
  - `raw_responses.json` -- every raw `/compose` response, verbatim, for
    every (target, run) pair. Nothing is discarded here.
  - `review.csv` -- one row per target, built for spreadsheet review:
    stability metrics, the modal odorant set, compatibility-warning hits,
    a sample justification, and two blank columns
    (`expert_reasonable_yn`, `expert_notes`) for your own judgment pass.

## Running it

Requires the AI backend running locally (default `http://localhost:8000`)
-- this hits the real `/compose` endpoint, i.e. real OpenAI API calls, real
cost, real latency. Not a mock or dry run.

```bash
cd "AI validation"

# Sanity check first -- 3 targets x 2 repeats, confirms the backend
# connection and output format work before spending real budget.
python3 run_validation.py --smoke

# Full run: 50 descriptors x 10 repeats (default) = 500 /compose calls.
python3 run_validation.py

# Just one cluster, e.g. re-testing only Putrid & Decay:
python3 run_validation.py --categories "Putrid & Decay"
```

Needs the `requests` package (`pip install requests` if not already in the
project's venv).

## Reading the output

Console output after a run prints the parts worth looking at first:
average stability, which targets had low set-stability (<60%), which
collapsed to a single odorant, which triggered a compatibility warning, and
which calls errored outright. `review.csv` has the full per-target detail
for everything else.

`set_stability` = fraction of repeats whose exact odorant set matched the
most common ("modal") set for that target. `dominant_stability` = same
idea, but just for whichever odorant had the highest `ratio` each run --
a softer signal, since the dominant note can stay stable even if a minor
supporting odorant varies between runs.

Note on interpreting stability post-ensemble-removal: as of this writing,
`ENSEMBLE_ENABLED=false` in `.env` -- every request (concrete or abstract)
goes through one single-shot model call, with no consensus voting forcing
repeat-consistency. Low stability here is a legitimate signal about the
base model's raw consistency now that the ensemble no longer masks it, not
a bug in this script.

Since this target list matches the human study's own taxonomy, it's also
worth comparing per-cluster AI stability against the human per-cluster
`exact`/`class` accuracy from that study (see the "Cluster accuracy
ranking" chart in the odorant dashboard) -- e.g. whether the AI is also
less consistent on the clusters humans found hardest to identify (Spice,
Fermented & Sour, Putrid & Decay scored lowest in the human study), or
whether AI and human failure patterns diverge.
