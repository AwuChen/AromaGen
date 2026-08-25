# AromaGen Final User Study

Single fixed 12-odorant set (no A/B condition), 50-word/12-cluster
descriptor taxonomy. Two sections per participant:

- **Section 1**: 12 3-AFC trials (one pass through all clusters), each
  followed by a feedback sub-flow (freeform or rating-scale, counterbalanced
  across participants).
- **Section 2 -- Freeform Aroma Recreation**: after Section 1, the
  participant does this 5 times: freely names a favourite
  food/beverage/perfume/memory/scene/abstract concept/any smell, the
  experimenter records what AromaGen produced for it, then the SAME KIND
  of feedback sub-flow runs (same counterbalanced freeform/rating-scale
  condition, reused for all 5) to iteratively refine that creation before
  moving to the next one.

## Revision history (high level)

1. Built as a copy of `../Internal Pilot Study/` with its own 50-word
   descriptor list and an A/B odorant-set condition (expert-chosen vs.
   PCA-derived).
2. **Odorant set is no longer a condition.** Every participant now uses
   the same single fixed 12-odorant set (below). Each participant does
   **one pass of 12 trials** (not two blocks of 12) -- there's nothing
   left to counterbalance block order against. `odorant_set` is still
   recorded on every trial/feedback row (constant value `"fixed_set"`)
   for logging consistency.
3. **Distractors are now chosen dynamically at runtime**, not looked up
   from a fixed table -- near distractors are randomly selected (weighted
   toward least-used-so-far) from the target's 2 ring-neighbor clusters,
   far distractor from the other family, against a running usage tally.
   This is what makes all 50 words appear roughly evenly as distractors
   across a batch of participants (verified: min/max usage spread of 1
   after 10 participants) while also varying which specific words get
   picked for a given target from one participant to the next.
4. **`trials` sheet**: `option_1_kind`/`option_1_word` (etc.) merged into
   one `option_1` column, formatted `"<word> (<kind>)"`, e.g.
   `"barbeque ribs (real near)"`.
5. **`feedback` sheet**: `initial_similarity_1to7` and
   `round_similarity_1to7` merged into one `similarity_rating` column.
   Round 0 (initial similarity) is always logged for every trial, with
   `round_input_text` fixed to `"THIS IS THE INITIAL ROUND FROM SYSTEM
   WITHOUT ANY FEEDBACK"`.
6. **Rating-scale screen overhaul**: a paste box for the system's initial
   composition (parses text like `"Clove Bud · 30% Vinegar · 40% Seaweed
   Accord · 30%"` and auto-populates the sliders, unmentioned odorants
   default to 0%), redesigned per-odorant cards (name + description on
   top, `[-] [======slider======] [+] [num%]` below, slider does most of
   the width), and a live-generated composition-request sentence ("Can you
   make Clove Bud 30%, Vinegar 40%, and Seaweed Accord 30%?") meant to be
   copied straight into AromaGen's feedback box.
7. **AromaGen's real frontend** (`aromagen/ui/demo/`) got a new **"Textual
   feedback"** button/textbox, wired to the exact same downstream code path
   as voice feedback (`processInputText` -> `feedbackScent`).
8. **Trial screen now captures AromaGen's target-reconstruction ratio.**
   The experimenter types what AromaGen's frontend shows for this trial's
   target (e.g. `"Vanilla · 60% Orange · 40%"`) into a new field on the
   4-AFC trial screen, right after the "Present the following 4 smells"
   step. Stored verbatim in the `trials` sheet as
   `llm_generated_base_odorant_ratio`.
9. **Rating-scale sliders now auto-initialize from that ratio** instead of
   an even split or a manual paste. `getPilotSessionView`
   (`PilotEngine.gs`) reads back this trial's captured ratio text via
   `getTrialLlmRatioText_`, parses it with `parseRatioText_`
   (`PilotData.gs`, the same regex logic the old paste-box used, now
   server-side), and falls back to an even split only if the text is blank
   or didn't parse to any known odorant. The **paste-box UI is removed** --
   there's nothing left to paste now that the ratio flows through
   automatically from the trial screen. The slider itself is now ~50% of
   its control row's width (`.ratio-slider { flex: 0 0 50%; }`), with the
   circular &minus;/+ buttons and a small number field around it.
10. **Rating-scale defaults now chain across feedback rounds.** Round 1's
    sliders still start from the trial screen's captured ratio, but round 2
    onward now start from whatever the PREVIOUS round's sliders were saved
    as (the resulting composition after that round's feedback), instead of
    resetting to the original ratio every round.
11. **The number field next to each slider is now much narrower**
    (`.ratio-num { width: 11px; }`, down from 56px) so the slider itself
    dominates the row.
12. **Section 2, "Freeform Aroma Recreation", added.** After Section 1's 12
    trials, a new briefing screen introduces a free-choice creation step;
    an intake screen captures what the participant asked AromaGen to make
    plus AromaGen's resulting base-odorant ratio; then the same feedback
    sub-flow as Section 1 runs once (initial rating + up to 5 rounds,
    freeform or rating-scale per the participant's existing counterbalanced
    condition) with rating-scale sliders auto-initializing from the
    captured ratio the same way Section 1's do. There's no real physical
    reference in Section 2, so the rating question asks how well the
    creation matches what the participant asked for/imagined, not how
    similar it is to a real object. Logged to a new `Freeform Creation`
    sheet, not `trials`/`feedback`. See "Section 2" below for details.
13. **Fixed a real bug in the rating-scale auto-init**, and made ratio-text
    parsing (`parseRatioText_`, `PilotData.gs`) more forgiving. The parser
    previously only matched the exact documented format (`"Name · NN%"`,
    number strictly after the name); it now also matches `"NN% Name"`
    (number first) and accepts `:`, `-`, `()`, or just whitespace as the
    separator, in addition to `·`. A bare number with no `%` sign is still
    left unparsed on purpose (e.g. `"Vanilla 0.5"` is ambiguous -- could
    mean 0.5% or a 0-1 fraction -- so it's not guessed). Both the trial
    screen's and Section 2 intake screen's ratio fields now show a live
    **"Parsed as: ..."** preview underneath as you type (green if it sums to
    100%, red otherwise or if nothing was recognized), using a client-side
    parser (`parseRatioTextClient_`, `DataCollection.html`) that mirrors
    the server one exactly -- so a typo or format mismatch is caught at
    entry time instead of silently falling back to an even split on the
    next screen.
14. **The rating-scale number field is removed.** Each odorant's value is
    now set ONLY via the slider (and the &minus;/+ buttons, which move the
    slider) -- no free-text number entry. The read-only percentage label
    above each slider still shows the current value for reference.
15. **Section 2 now runs 5 creations per participant, not 1.** The step
    machine (`STEP_SECTION2_START`..`STEP_SECTION2_END`, `PilotEngine.gs`)
    loops through `SECTION2_CREATIONS_PER_PARTICIPANT` (`PilotData.gs`,
    5) intake -> feedback cycles instead of a single one, mirroring Section
    1's per-trial loop. Per-creation intake data moved from two flat
    session columns (`section2_request_text`/`section2_llm_ratio`) to one
    JSON blob (`section2_creations_json`) keyed by `creation_index`, and
    the `Freeform Creation` sheet gained a `creation_index` column so its
    round-based feedback rows (upserted by participant + creation_index +
    round_number) can tell creations apart.
16. **Rating-scale rows are now ordered by their current value**, highest
    first, ties broken alphabetically -- not a fixed odorant order. Element
    IDs are keyed by each odorant's stable original index (`data-orig-index`
    on each card) rather than DOM position, so re-sorting never loses track
    of which slider is which. Re-sorts after any discrete edit (+/- click,
    slider release via `onchange`, Normalize) but NOT on every `oninput`
    tick while a slider is being actively dragged, since rebuilding the DOM
    node under the mouse mid-drag would break the gesture.
17. **Red "TEST ONLY: Skip to Section 2" button** added to the Section 1
    briefing screen -- jumps straight to the Section 2 briefing, skipping
    all 12 Section 1 trials, so Section 2 can be tested in isolation.
    Confirms before acting, and the server (`skipToSection2ForTesting`,
    `PilotEngine.gs`) rejects the call once `current_step` has moved past
    the briefing, so it can't be misused mid-session.
18. **Section 2's "initial match rating" step is removed.** Unlike Section
    1 (which rates the real physical reference against the ORIGINAL
    AromaGen reconstruction before any feedback), Section 2 has no real
    physical reference at intake time, so that first rating never made
    sense there. Now intake goes straight into feedback round 1 -- no
    rating screen in between. `submitSection2InitialMatch` (server) and its
    screen (client) are removed entirely; each feedback round still ends
    in its own rating, unchanged.
19. **Round 0 is back in the `Freeform Creation` sheet, but as a pure data
    log, not a separate UI page.** `submitSection2Intake` now immediately
    writes a `round_number = 0` row -- AromaGen's initial generated
    composition itself (the ratio the experimenter just typed, parsed into
    the same `round_ratios_json`/`resulting_composition_json` shape every
    later round uses). This gives a complete per-creation trail in one
    sheet: round 0 = what AromaGen first produced, rounds 1-5 = each
    feedback iteration's resulting composition + rating. `round_number = 0`
    is explicitly filtered out of `getPilotSessionView`'s Section 2
    `roundsSoFar`/`nextRoundNumber` (`upsertFreeformCreationRow_`,
    `PilotEngine.gs`), so it never appears as an editable "Feedback 0"
    block in the data-collection UI -- round 1 is still the first thing
    the experimenter can edit/save there.
20. **The intake screen now also collects "Rating in the first round"
    (1-7, same scale as every later round)**, stored as round 0's
    `match_rating_1to7` -- so round 0 isn't just the composition anymore,
    it's a complete rated data point like every other round, all captured
    on the one intake screen rather than a separate rating page.
    `submitSection2Intake` gained a 4th parameter (`initialRating1to7`,
    validated 1-7 server-side too).
21. **Fixed a real bug: rating values could display/read back as dates**
    like `"04/01/1900 00:00:00"` in `match_rating_1to7` /
    `similarity_rating`. The underlying number was never lost or wrong --
    Google Sheets can reinterpret a plain integer written into a cell as a
    date-serial number (day N after the Dec 30, 1899 epoch), and
    `Range.getValues()` then returns a JS `Date` for that cell instead of
    the number, regardless of what was actually written. Fixed by calling
    `.setNumberFormat("0")` on the specific cell immediately after every
    write to a ratings column (`forceNumberFormat_`, `PilotEngine.gs`),
    applied to `feedback.similarity_rating`, `Freeform
    Creation.match_rating_1to7`, and `trials.familiarity_1to7`/
    `confidence_1to7` (same latent risk, fixed preemptively). Any existing
    rows already showing a date instead of a number can be fixed by
    hand-selecting that column in Sheets and applying Format -> Number ->
    Plain number -- the underlying value has been the correct number all
    along.
22. **Section 2's briefing broadened what participants are prompted to
    recreate.** The read-aloud script (`renderSection2Briefing`,
    `DataCollection.html`) now suggests a favourite food, beverage,
    perfume, memory, scene, or abstract concept -- not just
    food/beverage/perfume -- so participants aren't steered toward only
    literal, concrete smells.
23. **9 descriptor words swapped** in `CLUSTERS` (`PilotData.gs`,
    `pilot_config.py`): Pine->birch, oak->patchouli, cherry
    blossom->rose, rose hand cream->cherry blossom cake, Wooden wine
    barrel->Whiskey and oak candle, Chai latte->chai tea, Coffee->coffee
    beans, barbeque ribs->korean bbq beef patty, Sticky tofu with
    chilli->Natto beans. Prospective only, per explicit instruction --
    changes what gets assigned to NEW participants going forward; any
    already-frozen `plan_json` (existing participants) keeps whatever
    words it was built with, untouched.
24. **The Section 1 initial-similarity screen now also shows the
    AromaGen-generated ratio** the experimenter typed on the preceding
    trial screen for this same trial (`llmRatioText`, threaded through
    `getPilotSessionView`'s `feedback` view in `PilotEngine.gs`, displayed
    in `renderInitialSimilarityForm_`, `DataCollection.html`). Lets the
    experimenter reliably re-trigger the exact same AromaGen composition
    on the device right before rating initial similarity, without having
    to recall or scroll back to what they entered a screen earlier.
25. **Section 1 changed from 4-AFC to 3-AFC.** Each trial now presents 3
    options instead of 4: the target + the same 2 near-class distractors
    as before (one realized as an AromaGen composition, the other as a
    real physical object), with the "far" distractor (drawn from the
    other family, realized as a real physical object) removed entirely.
    The near-distractor SAMPLING itself is unchanged -- still least-used-
    first from the target's 2 ring-neighbor clusters, random tie-break --
    only the far pick is gone (`pickDistractors_`, `PilotAssignment.gs`/
    `pilot_assignment.py`). `FAMILY_OF_CLUSTER` (its only consumer) is
    removed from `PilotData.gs`/`pilot_config.py`; `FAMILY_A_RING`/
    `FAMILY_B_RING` stay, since `NEIGHBOR_CLUSTERS` (near-distractor rings)
    is still built from them. **Prospective only**, per explicit
    instruction -- doesn't touch any already-frozen `plan_json`. The
    `trials` sheet's schema shrank from `option_1..option_4` to
    `option_1..option_3` -- unlike the earlier column-ADDITION migrations
    (`ensureSheetHeaders_` handles those safely), removing a column from
    the MIDDLE of the schema is NOT safely migratable: any already-
    collected `trials` rows would read misaligned under the new header.
    Delete any existing `trials` rows before running real 3-AFC sessions.
26. **Distractor design replaced entirely: exclusion lists instead of the
    family/ring system.** The old design (2 families of 6 clusters, each
    cluster with exactly 2 fixed ring-neighbor clusters as its near-
    distractor source) is gone. In its place, `EXCLUDED_CLUSTERS`
    (`PilotData.gs`/`pilot_config.py`) explicitly lists, per target
    cluster, which OTHER clusters may NOT supply distractors -- every
    other cluster (except the target's own, always implicitly excluded)
    is eligible, not just 2 fixed neighbors. Given verbatim by dictation
    for 10 of the 12 clusters; Spice's and Perfumed & Clean's entries were
    never dictated directly but are fully recoverable by symmetry (a
    handful of dictated pairs were one-directional and were made mutual
    per explicit confirmation -- e.g. Citrus excluded Woody & Resinous but
    not vice versa in the raw dictation). `FAMILY_A_RING`/`FAMILY_B_RING`/
    `ringNeighbors_`/`NEIGHBOR_CLUSTERS` are removed entirely (no consumer
    left). Distractor SELECTION within the eligible pool now has two
    layered rules instead of one: (1) a NEW hard per-cluster non-repeat
    cycle -- `clusterUsedSets`/`cluster_used_sets`, tracking every word
    already used as a distractor for a given target cluster across every
    participant so far; a word can't repeat for that cluster until every
    eligible word has been used once, then the cycle resets -- and (2) the
    existing least-used-first balancing against the running GLOBAL
    `distractorTally`, unchanged, so overall usage still stays even across
    all 50 words. `clusterUsedSets` is reconstructed fresh from history on
    every call (`computeClusterUsedSets_`, `PilotData.gs`), replaying each
    historical trial's pair of distractor words as a single unit (checked
    once per trial, not per word) -- this side-steps an unrecoverable
    ambiguity in the stored data (which of a trial's 2 distractor words was
    picked "first" isn't independently retrievable, since which one became
    `aromagen_near` vs `real_near` is separately randomized). **Prospective
    only**, same as revision 25 -- doesn't touch already-frozen plans.
27. **Added one more mutual exclusion: Woody & Resinous &harr; Chemical &
    Solvent.** Per explicit follow-up instruction -- a Woody & Resinous
    target can no longer draw a Chemical & Solvent distractor, and vice
    versa. Both clusters' eligible pools shrink from 6 to 5 clusters as a
    result (now tied with Herbal & Cooling as the most restricted).
    Prospective only, same as revisions 25-26.
28. **Added a ratio-source condition, independent of feedback_type.** A
    second per-participant condition (`plan.condition`, `"ai"` or
    `"expert"`), chosen via a new Admin Panel toggle at generation time.
    Does NOT touch target/distractor selection, balancing, or eligibility
    at all -- CLUSTERS/EXCLUDED_CLUSTERS/tallies are identical either way.
    The only difference: in the `"expert"` condition, every smell shown to
    the experimenter (the trial's target, both AromaGen-realized options
    -- the true target and the AromaGen-composed near distractor, not the
    real-object distractor -- and the cartridge-check target list) also
    displays a fixed expert-derived base-odorant ratio looked up from
    `EXPERT_RATIOS` (`PilotData.gs`/`pilot_config.py`), instead of (or
    alongside) the experimenter generating one live via the AromaGen app.
    `EXPERT_RATIOS` is now filled in for all 50 descriptors, sourced from
    the expert panel's normalized, majority-selected formulation per
    target (3-expert rating process; the highest-rated expert's
    formulation was taken per target, 29/50 from Expert 2, 16/50 from
    Expert 1, 5/50 from Expert 3). If `EXPERT_RATIOS` is ever short a
    word in the future (e.g. a new descriptor is added without updating
    the table), the panel degrades gracefully to a "not yet set" note
    for just that word rather than erroring. Prospective only, same as
    revisions 25-27 -- already-generated participants keep whatever
    condition (implicitly `"ai"`) they were generated under.

```
Benz Sal                              Perfumed / Clean       vol 4
Sandalwood                            Woody / Resinous       vol 3
Clove Bud + Cumin                     Spice                  vol 6
Lavender + Rose                       Floral                 vol 5
Orange + Lemon                        Citrus                 vol 8
Vanilla Sugar + Almond Extract        Sweet / Gourmand       vol 3
Birch tar oil + Coffee + Clove Bud    Roasted / Smoky        vol 4
Eucalyptus                            Herbal / Cooling       vol 8
Cognac                                Chemical / Solvent     vol 8
Vinegar                               Fermented / Sour       vol 8
Isovaleric acid                       Animal / Body          vol 7
Seaweed + Fenugreek + Garlic          Umami / Savoury        vol 6
```

Matches the live AromaGen catalog (`aromagen/cartridge_sets.json`) exactly
as of revision 28 -- 6 of the 12 slots are now multi-ingredient blends
rather than single raw materials (renamed over the course of production
tuning; see `aromagen/cartridge_sets.json`'s own history for why).
`cartridge_configs/cartridge_sets.json` is a snapshot copy for reference
(re-sync if the live catalog changes again).

## The 50-word / 12-cluster descriptor list

9 words swapped in the most recent revision (see revision 23 below) --
prospective only, does not touch any already-frozen participant plan:

```
Floral: Lavender, rose, jasmine tea, cherry blossom cake
Citrus: Orange, mango, Lemonade, Lime soda (Sprite)
Woody & Resinous: birch, patchouli, Whiskey and oak candle, Incense
Herbal & Cooling: Basil, Cucumber, Peppermint tea, Mint chewing gum
Spice: Ginger, Black pepper, chai tea, Cinnamon roll
Sweet & Gourmand: Coke, dark chocolate, Apple pie, Sweet popcorn, chocolate and marshmallow-flavored pop tarts
Roasted & Smoky: coffee beans, Bacon, korean bbq beef patty, Hot dog with hot sauce
Fermented & Sour: Greek yogurt, Pickled cucumber, Fries with ranch sauce, Nacho with sour cream
Putrid & Decay: Blue cheese, durian, Canned sardines, Natto beans
Chemical & Solvent: Whiskey, Tequila, Mint Fluoride mouthwash, Lavender nail polish remover
Perfumed & Clean: Aloe vera, Hand sanitizer, Mint fluoride toothpaste, Almond oil shampoo
Savoury & Umami: Soy sauce, Parmesan cheese, Garlic, Seasoned pull pork in bbq sauce, Salty popcorn
```

## Dynamic distractor selection

Each trial's 2 distractors are drawn from an EXCLUSION-LIST-derived pool,
not a fixed neighbor/ring structure (see revision 26 above for the design
history). `EXCLUDED_CLUSTERS` lists, per target cluster, which other
clusters are OFF LIMITS as a distractor source -- every remaining cluster
(other than the target's own) is fair game:

```
Floral:              excludes Woody & Resinous, Herbal & Cooling, Perfumed & Clean
Citrus:               excludes Woody & Resinous, Sweet & Gourmand, Chemical & Solvent, Herbal & Cooling
Woody & Resinous:     excludes Floral, Herbal & Cooling, Spice, Citrus, Putrid & Decay, Chemical & Solvent
Herbal & Cooling:     excludes Floral, Citrus, Woody & Resinous, Spice, Sweet & Gourmand, Chemical & Solvent
Spice:                excludes Woody & Resinous, Herbal & Cooling, Sweet & Gourmand
Sweet & Gourmand:     excludes Citrus, Herbal & Cooling, Spice
Roasted & Smoky:      excludes Savoury & Umami, Fermented & Sour
Fermented & Sour:     excludes Roasted & Smoky, Putrid & Decay, Savoury & Umami
Putrid & Decay:       excludes Fermented & Sour, Savoury & Umami, Woody & Resinous
Chemical & Solvent:   excludes Perfumed & Clean, Citrus, Herbal & Cooling, Woody & Resinous
Perfumed & Clean:     excludes Floral, Chemical & Solvent
Savoury & Umami:      excludes Fermented & Sour, Roasted & Smoky, Putrid & Decay
```

Every pair is symmetric (if A excludes B, B excludes A) -- eligible pool
sizes range from 5 clusters (Herbal & Cooling and Woody & Resinous, the
most restricted) to 9
(Roasted & Smoky and Perfumed & Clean, the least). Within the eligible
pool, the actual WORD chosen is governed by two layered rules, applied at
plan-build time:

1. **Hard per-cluster non-repeat cycle**: a word already used as a
   distractor for a given target cluster can't be picked again for that
   cluster until every eligible word for it has been used once, at which
   point the cycle resets. Tracked via `clusterUsedSets`
   (`PilotEngine.gs`/`PilotAssignment.gs`) / `cluster_used_sets`
   (`pilot_assignment.py`), reconstructed fresh from every session's
   frozen `plan_json` before each new plan is built
   (`computeClusterUsedSets_`).
2. **Least-used-first, globally**: among whatever's left after rule 1,
   picked as the least-used-so-far candidate (random tie-break) against a
   running distractor-usage tally -- same balancing principle used for
   target selection, mutated across every trial as plans are built.

Verified via `pilot_assignment.py`: after 10 participants, all 50 words
have been used as a distractor 4-6 times each (spread of 2 -- Woody &
Resinous and Chemical & Solvent's now-smaller eligible pools, 5 clusters
each after excluding each other too, spread usage slightly less evenly
than the rest), and the hard non-repeat cycle held for every cluster
across the whole run (no word repeated as that cluster's distractor
before its eligible pool was
exhausted once).

## The feedback sub-flow

Unchanged in structure from the previous revision (initial similarity +
up to 5 rounds, freeform/rating-scale counterbalanced by participant
parity), except:
- The initial-similarity instruction no longer references "the option
  they just judged" -- the comparison happens regardless of whether the
  3-AFC answer was correct.
- Round 0 (initial similarity) is always logged, with a fixed marker
  string in `round_input_text` instead of a separate column.
- All similarity ratings (round 0 and rounds 1-5) share the single
  `similarity_rating` column.

### Rating-scale round, redesigned

1. **Sliders auto-initialize** from the ratio text captured on the trial
   screen (Section 1) / intake screen (Section 2) for round 1, then from
   the previous round's saved ratios for round 2+ -- no manual paste step.
   Parsing (`parseRatioText_`, `PilotData.gs`) searches for each known
   odorant name next to a percentage, name-first or number-first, with a
   loose separator (`·`, `:`, `-`, `()`, or just whitespace); anything not
   mentioned is set to 0%. A live "Parsed as: ..." preview under the ratio
   text field (trial/intake screen) shows exactly what will be used, before
   moving to the next screen.
2. **Per-odorant cards**: name + short description up top, then a control
   row with a circular &minus; button, a slider (~50% of the row's width),
   and a circular + button -- the slider is the ONLY way to set the value,
   there's no free-text number field. The read-only percentage label above
   the slider shows the current value.
3. **Cards are ordered by their current ratio, highest first** (ties broken
   alphabetically), not a fixed odorant order -- re-sorting live as values
   change. Order updates after a slider is released, a &minus;/+ click, or
   Normalize; not on every tick while a slider is being dragged, so drag
   gestures stay smooth.
4. **Live sum indicator** + a "Normalize to 100%" button (proportionally
   rescales all current values to sum to exactly 100%). The save button is
   disabled until the sum is exactly 100% (small floating-point tolerance).
5. **Live composition-request sentence**: updates as sliders move, e.g.
   *"Can you make Clove Bud 30%, Vinegar 40%, and Seaweed Accord 30%?"* --
   meant to be copied directly into AromaGen's new "Textual feedback" box
   (see below) so the experimenter doesn't have to compose the request by
   hand.

## Section 2: Freeform Aroma Recreation

Runs after all 12 Section 1 trials are complete: one briefing, then
`SECTION2_CREATIONS_PER_PARTICIPANT` (`PilotData.gs`, currently **5**)
separate creations back to back, each its own intake -> feedback cycle --
mirroring Section 1's overall briefing -> (per-item content -> feedback)
shape, just with "creation" in place of "trial."

1. **Briefing** (`section2_briefing`, once): tells the participant they'll
   freely choose a favourite food/beverage/perfume/memory/scene/abstract
   concept/any smell, 5 times, and AromaGen will try to recreate each one.
2. **Intake** (`section2_intake`, once per creation): the experimenter
   enters (a) what the participant asked AromaGen to create this time, in
   their own words, (b) AromaGen's resulting base-odorant ratio (same
   `"Vanilla · 60% Orange · 40%"` format as the Section 1 trial screen),
   and (c) a rating for that first result (1-7, same scale as every later
   round). (a)+(b) are stored in the session row's `section2_creations_json`
   blob, keyed by `creation_index` (`getSection2CreationsMap_`/
   `getSection2Intake_`, `PilotEngine.gs`) -- analogous to how Section 1's
   `plan_json` holds every trial's data centrally. Submitting also
   immediately logs `round_number = 0` to the `Freeform Creation` sheet:
   the initial AromaGen-generated composition plus that rating, so there's
   a complete rated data point even before any feedback happens.
3. **Feedback** (`section2_feedback`, once per creation): up to 5 rounds,
   freeform or rating-scale per the participant's existing counterbalanced
   `feedback_type` (not re-randomized per creation), served by the same
   shared rendering code (`renderFeedbackRoundsCore_`,
   `wireUpFeedbackRoundForm_`, etc. in `DataCollection.html`, parameterized
   by a `mode` of `'section1'`/`'section2'` to pick the right RPC
   endpoints). Unlike Section 1, there's **no initial-RATING step before
   round 1** in the UI -- intake flows straight into feedback round 1 on
   screen, since there's no real physical reference yet to rate against at
   that point (round 0 exists in the SHEET, per above, just not as
   something the experimenter fills in). Each round still ends in its own
   rating: how well the creation matches what the participant asked
   for/imagined (1 = not at all what they wanted, 7 = exactly what they
   wanted), not perceptual similarity to a real object (Section 1's
   framing).

Finishing a creation's feedback (`finishSection2Feedback`) advances to the
next creation's intake, exactly like `finishTrialFeedback` advances between
Section 1 trials -- except on the 5th (last) creation, it instead marks the
session/participant `"completed"`, the true end of the study.

## AromaGen frontend change: "Textual feedback"

`aromagen/ui/demo/index.html` / `script.js` -- a new button next to the
existing direct-text-input row. Clicking it reveals a text input + "Send
feedback" button. Submitting calls `processInputText(feedbackText)`
**without** `forceCompose`, which is the exact same call the transcribed-
voice-recording path makes -- so it gets identical downstream treatment:
routes to `feedbackScent()` if a composition is already active
(`isInFeedbackMode`), or starts a fresh composition otherwise. This is a
change to the real product, not just the study tooling -- it's what the
rating-scale composition-request sentence above is meant to be pasted
into during a real session.

## IMPORTANT LIMITATION: no live connection to AromaGen's frontend

Unchanged from the previous revision -- Apps Script has no network path to
your local AromaGen backend/frontend. The trial screen's new ratio field
is how the real starting composition gets in without a live connection:
the experimenter reads it off AromaGen's frontend and types it in once per
trial; the rating-scale feedback screen then reuses that same text to
initialize its sliders. If that field is left blank (or doesn't parse),
sliders fall back to an even split. Every field is editable afterward.

## Deploy

Same deployment as before (redeployed in place, not a new project):
```
https://script.google.com/macros/s/AKfycbxEfdZWHVxCZRhvgdBtDiDzjY87StO9yz-MpE3Gg4ZkY95BLMcselMFAmyFqDb_Dls-/exec?admin=<your token>
```
Script editor (for re-authorization if needed):
```
https://script.google.com/d/1fN6Qly8_Z4VTzIRYv12ak_P1hhqn8lNvt8vUiqAzTcHBN1Ugr1vZY2fY/edit
```

**The admin token stays the same across redeploys** so this link doesn't
change every time the code is updated. It's kept in `.admin_token`
(git-ignored, next to this README, never committed) -- the redeploy
process reads that value, temporarily writes it into `Code.gs`'s
`ADMIN_TOKEN` for `clasp push`/`clasp deploy`, then reverts `Code.gs` back
to the `REDACTED_SET_YOUR_OWN_TOKEN_HERE` placeholder before finishing, so
the tracked source never carries the real value. If `.admin_token` is ever
lost, generate a new one (`node -e "console.log(require('crypto').randomBytes(24).toString('hex'))"`),
save it to that file, and redeploy once -- every previously shared link
will need updating at that point, so this is meant to be a rare event, not
routine.

**If you already created test participants under the previous (two-block,
A/B) schema**, note that the master spreadsheet's headers were set once at
spreadsheet-creation time and won't auto-migrate -- delete the old
"AromaGen Final User Study - Master Data" spreadsheet and its
`AROMAGEN_FINAL_STUDY_MASTER_SPREADSHEET_ID` Script Property (or just let
`getOrCreatePilotMasterSpreadsheet_` create a fresh one under a new
property key) before running real participants, so old-format rows don't
sit alongside new-format ones. As of this revision, no real participant
data is believed to exist yet -- only page-load checks were done, no
`generateParticipantsBatch`/`startPilotSession` calls.

## What's in the master spreadsheet

("AromaGen Final User Study - Master Data")

- **participants**: name, sequence index, `odorant_set` (constant),
  `feedback_type`, status, timestamps.
- **sessions**: frozen plan (`plan_json`), current step, `trial_phase`
  ("afc" | "feedback" | "intake"), status, `section2_creations_json` (JSON
  blob of `{creation_index: {requestText, llmRatioText}}`, one entry per
  Section 2 creation, written incrementally as each creation's intake
  screen is submitted).
- **trials**: `participant_name`, `odorant_set`, `trial_index`, `target`,
  `cluster`, `option_1`..`option_3` (merged `"<word> (<kind>)"` format --
  3-AFC as of revision 25, was `option_1`..`option_4`),
  `correct_slot`, `familiarity_1to7`, `selected_slot`, `is_correct`,
  `confidence_1to7`, `response_timestamp`,
  `llm_generated_base_odorant_ratio` (experimenter-entered, e.g. `"Vanilla
  · 60% Orange · 40%"`).
- **feedback** (Section 1): `participant_name`, `trial_index`, `target`,
  `odorant_set`, `feedback_type`, `round_number` (0 = initial similarity,
  1-5 = feedback rounds), `round_input_text`, `round_ratios_json`,
  `resulting_composition_json`, `similarity_rating`, `response_timestamp`.
  Upserted by (participant, trial, round_number) -- editing a round
  updates its row in place.
- **Freeform Creation** (Section 2): `participant_name`, `creation_index`
  (1-5), `feedback_type`, `request_text`, `llm_generated_base_odorant_ratio`,
  `round_number` (0 = AromaGen's initial generated composition + the
  intake screen's "Rating in the first round" value, logged the moment
  intake is submitted; 1-5 = feedback rounds, each with its own
  `match_rating_1to7`), `round_input_text`, `round_ratios_json`,
  `resulting_composition_json`, `match_rating_1to7`, `response_timestamp`.
  Upserted by (participant, creation_index, round_number). Round 0 is
  written by `submitSection2Intake` but excluded from the data-collection
  UI's round list -- it's a data-only record, not something the
  experimenter edits.

## Known limitations, stated rather than papered over

1. **Not yet tested end-to-end in a browser by a human**, including the
   redesigned rating-scale UI, the ratio-auto-fill flow (trial screen ->
   feedback screen, and now intake screen -> Section 2 feedback screen),
   `ensureSheetHeaders_`'s column-migration path, and all of Section 2.
   Test with P1 (freeform) and P2 (rating-scale) through BOTH sections
   before a real session.
2. **No live AromaGen connection** -- see above.
3. **No response-time data** -- not captured by this pipeline.
4. **(FIXED, kept for history)** `ensureSheetHeaders_` used to compare the
   current schema's prefix against `sheet.getLastColumn()`'s width, which
   reflects the sheet's widest-EVER-used column, not row 1's actual
   content -- it's sticky across schema changes and doesn't shrink just
   because a later header rewrite only touched the first N cells. On this
   spreadsheet that meant the `trials` header silently accumulated stale
   "ghost" columns from an older, wider schema (duplicate
   `is_correct`/`confidence_1to7`/`response_timestamp` labels sitting past
   column 15) and permanently skipped adding the real new column,
   `llm_generated_base_odorant_ratio` -- every row kept writing that ratio
   text into column 16 with no header above it. Fixed: `ensureSheetHeaders_`
   now compares row 1 directly against `SHEET_SCHEMAS_[name]` and rewrites
   positions 1..N on ANY mismatch (clearing stale ghost cells past N too),
   rather than trying to cleverly detect "just grew." Confirmed via a
   temporary debug dump that the live `trials` header self-healed to the
   correct 16 columns after this fix deployed.
5. **Ratio-text parsing still requires a `%` sign on each number.** A bare
   fraction like `"Vanilla 0.5"` (meaning 50%) is deliberately left
   unparsed rather than guessed, since it's ambiguous with "0.5%". The live
   "Parsed as:" preview (trial/intake screens) makes this visible
   immediately -- if it shows the wrong thing or nothing, add a `%` sign.
6. **(FIXED, real live bug, kept for history)** Every "real far" distractor
   option in every trial for every participant showed up with no `word`
   (literal `"undefined (real far)"` in the `trials` sheet / on-screen) --
   100% of trials, not intermittent. An EARLIER investigation into this
   (when only 2 old test participants, `T1`/`T2`, showed it) wrongly
   concluded it was stale data frozen under some past buggy code version,
   since a 500-participant Node.js simulation of the exact deployed
   `PilotAssignment.gs`/`PilotData.gs` source found zero occurrences --
   that conclusion was **wrong**. The bug was live and affected every
   participant, including brand new ones; the simulation just couldn't see
   it because of how it was built.

   **Real root cause**: `PilotAssignment.gs` had `var ALL_WORDS_ = (function
   () { ... for (var c in CLUSTERS) ... })();` -- an IIFE that runs
   IMMEDIATELY when the file's top-level code executes. Apps Script
   concatenates a project's `.gs` files and runs their top-level statements
   in FILENAME-ALPHABETICAL order before any function is ever called:
   `"PilotAssignment.gs"` sorts before `"PilotData.gs"` (`'A' < 'D'`), so
   that IIFE ran while `CLUSTERS` (declared in `PilotData.gs`) was still
   `undefined` -- hoisted but not yet assigned. `for (var c in undefined)`
   doesn't throw, it just iterates zero times, so `ALL_WORDS_` silently
   became `[]` forever, and every far-distractor pick
   (`ALL_WORDS_.filter(...)` in `pickDistractors_`) filtered an empty array
   and returned `undefined`.

   Every Node.js simulation used to "prove" this was fixed had concatenated
   `PilotData.gs` before `PilotAssignment.gs` (the logically correct
   dependency order) -- masking the exact failure mode, since it only
   happens under Apps Script's alphabetical load order. Reproduced directly
   by simulating the real file order (confirmed `ALL_WORDS_.length === 0`,
   12/12 trials broken); confirmed fixed the same way after the change
   (`ALL_WORDS_.length === 50`, 0/500 simulated participants broken).

   **Fix**: `ALL_WORDS_` is now computed lazily inside a memoized
   `allWords_()` function instead of an eager top-level IIFE, so it only
   runs the first time something actually calls it -- by then every file's
   top-level code has finished executing, in any file order, so `CLUSTERS`
   is guaranteed to be assigned.

   **Any participant created before this fix has a permanently corrupted
   frozen plan** (plans are frozen into `plan_json` at first creation and
   never regenerated) -- delete their rows from
   `participants`/`sessions`/`trials`/`feedback`/`Freeform Creation` (or
   just re-generate them under new names) before treating them as real
   data. `T1` also reached the OLD single-creation Section 2 under an even
   older schema (flat `section2_request_text`/`section2_llm_ratio` session
   columns, no `creation_index`) -- that data is orphaned rather than
   misread, but delete it anyway.
