# AromaGen Internal Pilot Study

A/B tests two 12-odorant sets against each other -- an **expert-chosen**
set vs. a **PCA-derived** set -- for overall accuracy, cluster-level
accuracy, and qualitative feedback. Tests the *whole AromaGen pipeline*
(AI composition + physical device + human identification) for each
candidate odorant set, not raw single-material sniff identification --
materially different protocol from the sibling `../Preliminary Study/`.

**Descriptor taxonomy is its own list, scoped to this pilot only**: 11
clusters, 46 words (drops "Body & Animalic" relative to the Preliminary
Study's 12-cluster/50-word list -- these are two separate, non-interchangeable
taxonomies). Each block = one target per cluster = 11 trials; two blocks
per participant (one per odorant-set condition) = **22 total trials per
participant**.

## Files

- `pilot_config.py` -- shared taxonomy (11 clusters / 46 words),
  distractor table, and the two odorant-set definitions (Python).
- `pilot_assignment.py` -- validated prototype of the balancing +
  counterbalancing logic. Run `python3 pilot_assignment.py` to see the
  per-condition coverage and block-order counterbalance checks.
- `apps_script/` -- the real, deployable system:
  - `PilotData.gs` -- taxonomy/config (ported from `pilot_config.py`) +
    spreadsheet schema/plumbing. `TRIALS_PER_BLOCK` (= 11) drives the
    session engine's step math -- if the descriptor list's cluster count
    changes again, update it here and in `pilot_config.py`, nothing else
    needs to change.
  - `PilotAssignment.gs` -- ported from `pilot_assignment.py`.
  - `PilotEngine.gs` -- the session state machine. Step boundaries
    (`STEP_*` constants) are derived from `TRIALS_PER_BLOCK`, not
    hardcoded -- see its own docstring for the numbering.
  - `Code.gs` -- web app entry point, admin-token gate, routes between
    the two pages below.
  - `AdminPanel.html` -- generate participants (single or batch), review
    descriptor coverage, get each participant's data-collection link.
  - `DataCollection.html` -- the actual trial-running flow for ONE
    participant, loaded via the link the admin panel gives you (reads
    `pid` from the URL, no manual entry).
  - `appsscript.json` -- manifest.
- `cartridge_configs/` -- two ready-to-swap AromaGen catalog files:
  - `cartridge_sets_pca.json` -- copy of the live
    `aromagen/cartridge_sets.json` as of this pilot's setup (the
    "PCA-derived" condition).
  - `cartridge_sets_expert.json` -- **placeholder** 12-odorant catalog
    (named `A`-`l`, matching the literal placeholder list given when this
    was set up) for the "expert-chosen" condition. Replace with real
    odorant data before running any real session -- see below.

## The two conditions, and what's still a placeholder

- **PCA-derived** = the odorant set currently live in the actual AromaGen
  system (12 odorants: Benz Sal, Sandalwood, Clove Bud, Lavender, Orange,
  Vanilla, Birch tar oil, Eucalyptus, Cognac, Vinegar, Isovaleric acid,
  Seaweed Accord -- re-synced 2026-08 after Seaweed Accord was added as a
  12th odorant to the live catalog).
- **Expert-chosen** = given as literal placeholders (`A, B, C, D, E, f, g,
  h, i, j, k, l`) pending the real 12 expert-chosen odorants.

Both sets are now 12 odorants each -- the earlier size mismatch (11 vs 12)
is resolved. If the live AromaGen catalog changes again, re-sync
`PCA_DERIVED_SET` in `pilot_config.py` and `PilotData.gs`, plus
`cartridge_configs/cartridge_sets_pca.json`.

**To fill in the real expert-chosen set**, update in three places (kept
deliberately redundant since Python and Apps Script are separate
runtimes): `pilot_config.py`'s `EXPERT_CHOSEN_SET`, `PilotData.gs`'s
`EXPERT_CHOSEN_SET`, and `cartridge_configs/cartridge_sets_expert.json`.

## The distractor table mirrors the Preliminary Study's ring design

The Preliminary Study split its 12 clusters into two families of 6, gave
each cluster 2 fixed near-neighbor clusters within its own family (a
"ring" the user specified explicitly), and drew one near-distractor word
from each neighbor cluster; the far distractor came from the other family,
balanced. No equivalent ring was given for this 46-word list, so the
family split + ring below is a **proposed analogous structure, confirmed
with the user** before implementing (not hand-specified word-by-word like
the original):

- **Family A** (6 clusters, ring order): Floral &harr; Sweet & Gourmand
  &harr; Spice &harr; Woody & Resinous &harr; Herbal & Cooling &harr;
  Citrus &harr; (back to Floral)
- **Family B** (5 clusters, ring order): Perfumed & Clean &harr; Roasted
  & Smoky &harr; Fermented & Sour &harr; Putrid & Decay &harr; Chemical &
  Solvent &harr; (back to Perfumed & Clean)

For each target: the 2 near distractors are the least-used-so-far word
from each of its 2 ring-neighbor clusters (least-used-first balancing,
not hand-picked); the far distractor is the least-used-so-far word from
the *other* family entirely. Verified: near-distractor usage ranges 1-3
across all 46 words, far-distractor usage ranges 0-2, no target is its
own distractor, no duplicate distractors within a trial.

**Which near distractor becomes the AromaGen composition vs. the real
physical object is randomized per trial** (coin flip, in `build_trial()`/
`buildTrial_()`) -- not fixed by table position. This was originally fixed
(table position 0 always AromaGen) and was changed to randomized per
explicit request.

If you want a hand-curated table instead of this ring-generated one,
replace `DISTRACTOR_TABLE` in both `pilot_config.py` and `PilotData.gs`.

## The trial protocol

Each **participant** does **two blocks**, one per odorant-set condition,
11 trials each (one target descriptor per cluster). **Block order is
counterbalanced** by participant sequence position -- odd-numbered
participants (1st, 3rd, 5th enrolled) get the expert-chosen set first;
even-numbered get the PCA-derived set first. Descriptor coverage is
balanced *within each condition independently* (least-used-first), so
after ~10 participants each of the 46 words has been tested roughly
equally often under *each* odorant set, not just in aggregate.

Each **trial**:
1. Participant is told the target word, then smells a **real physical
   reference example** of it directly (not one of the 4 comparison
   options -- just an anchor). Rates familiarity 1-7.
2. Presented with 4 smells in sequence, numbered 1-4 (shuffled
   presentation order each trial):
   - **AromaGen target reconstruction** -- the device, composing the
     target word using the block's active odorant set. Always the correct
     answer.
   - **AromaGen near distractor** -- the device, composing a
     same-cluster distractor word.
   - **Real near distractor** -- a real physical object for a second
     same-cluster distractor word.
   - **Real far distractor** -- a real physical object for an
     other-cluster distractor word.
3. Participant picks which of the 4 numbered smells matches the target.
   Rates confidence 1-7.
4. 10-second enforced break (countdown in the control panel) before the
   next trial.

After 11 trials, a rest + cartridge-swap screen shows the next block's
odorant set and its 11 targets (a sanity check for the experimenter),
then the second block runs the same way.

## Two-page architecture

- **Admin Panel** (`?admin=<token>`) -- paste one or many participant
  names (newline/comma-separated), click Generate. Skips names already
  generated (idempotent -- safe to re-paste a longer list later) but
  still returns their link. Shows a table: name, generated/already-existed
  status, block order, direct data-collection link. Also has a
  descriptor-coverage table and the master-spreadsheet link.
- **Data Collection Panel** (`?admin=<token>&pid=<name>`) -- opened via
  the link the admin panel gave you. Auto-loads that participant's
  session on page load (resumes wherever they left off if reopened).
  Screens, in order:
  1. **Briefing** -- standard HCI study briefing text (edit directly in
     `DataCollection.html`'s `renderBriefing()` for different wording).
     Participant gets blindfolded here; the experimenter operates the
     panel on their behalf from this point on.
  2. **Cartridge check** -- active odorant set + its 11 upcoming targets,
     to confirm the physical cartridge matches before starting.
  3. **Trial** (x11 per block) -- target word, familiarity input, the 4
     options with explicit prepare/trigger instructions, selected-slot
     input, confidence input, then the 10s countdown.
  4. **Rest + cartridge check** for block 2, then 11 more trials, then
     **done**.

Both pages require the admin token (not just `pid` alone, unlike the
Preliminary Study's open participant links) -- every screen here reveals
correct answers, and no real participant ever opens either page
themselves.

## IMPORTANT LIMITATION: this cannot trigger AromaGen or dispense anything

Google Apps Script runs in Google's cloud -- it has no network path to
your local AromaGen backend (`localhost:8000`) or the device's Bluetooth
connection, and can't dispense real physical objects either. This system
handles sequencing, balancing, counterbalancing, timing, and data logging
*only*. Every trial screen tells the experimenter exactly what to prepare
or trigger; the experimenter operates the actual AromaGen frontend/device
and sources the real physical objects themselves, side-by-side with this
panel.

**When swapping the physical cartridge between blocks**, also point the
live AromaGen backend at the matching catalog file so `/compose` calls
during that block actually draw from the correct odorant set:

```bash
# expert-chosen block:
CARTRIDGE_SETS_PATH="/path/to/cartridge_configs/cartridge_sets_expert.json" <restart backend>

# PCA-derived block:
CARTRIDGE_SETS_PATH="/path/to/cartridge_configs/cartridge_sets_pca.json" <restart backend>
```

## Deploy

1. [script.google.com](https://script.google.com) -> New project.
2. Create `PilotData.gs`, `PilotAssignment.gs`, `PilotEngine.gs`, `Code.gs`
   (Script type) and `AdminPanel.html`, `DataCollection.html` (Html type),
   copying contents exactly. Set `appsscript.json` via Project Settings ->
   "Show appsscript.json manifest file".
3. Set your own `ADMIN_TOKEN` in `Code.gs` (generate via
   `node -e "console.log(require('crypto').randomBytes(24).toString('hex'))"`)
   -- the committed copy has it redacted.
4. Deploy -> New deployment -> Web app. Execute as **Me**, access
   **Anyone**.
5. Your admin panel URL is the deployment URL + `?admin=<your token>`.

(This project was also deployed live via `clasp` during development --
if you have the script ID, `clasp push` + `clasp redeploy <deploymentId>`
updates the same URL without going through the manual steps above.)

## What's in the master spreadsheet

("AromaGen Internal Pilot Study - Master Data", auto-created on first use)

- **participants**: one row per participant -- name, sequence index, block
  order, status, timestamps.
- **sessions**: internal engine state -- the frozen plan (`plan_json`,
  both blocks' full trial detail including correct answers), current step,
  status. Don't edit; inspect if something looks wrong.
- **trials**: one row per (participant, trial) across both blocks --
  block index, odorant set, target, cluster, all 4 options with their kind
  (aromagen_target/aromagen_near/real_near/real_far) and word, correct
  slot, familiarity, selected slot, correctness, confidence, timestamp.
  The tidy table for accuracy/cluster-accuracy analysis, joinable by
  `odorant_set` to compare the two conditions directly.

## Known limitations, stated rather than papered over

1. **Not fully tested end-to-end in a browser by a human.** The
   assignment logic is verified (Python prototype, `pilot_assignment.py`),
   the deployment is live and the admin panel confirmed reachable, but a
   full click-through (briefing -> cartridge check -> all 11 trials of
   block 1 -> rest -> all 11 trials of block 2 -> done) hasn't been
   observed firsthand. Test with 1-2 dummy participants first.
2. **Qualitative feedback** has no dedicated collection screen -- add one
   if you want it; `submitTrial`/`advanceStep_` in `PilotEngine.gs` is a
   template for adding another screen and sheet column.
3. **No response-time data** -- not captured by this pipeline.
