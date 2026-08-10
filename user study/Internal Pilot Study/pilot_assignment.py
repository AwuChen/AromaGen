"""
Prototype/validation sandbox for the Internal Pilot Study's assignment
engine -- same relationship to `apps_script/PilotAssignment.gs` as
`../Preliminary Study/study_design.py` had to that study's `Assignment.gs`:
this is where the logic gets designed and checked before being ported 1:1
into Apps Script, which is the real, deployed system.

Design, per the study's actual purpose (A/B testing the "expert-chosen" vs.
"PCA-derived" 12-odorant sets for overall accuracy, cluster-level accuracy,
and qualitative feedback):

- Each PARTICIPANT does TWO BLOCKS in one session: one block per odorant
  set. Each block = one target descriptor per cluster (TRIALS_PER_BLOCK =
  len(CLUSTERS), currently 11, so both blocks give full cluster coverage --
  22 trials/participant total), independently sampled from the same
  46-word pool. This is a SEPARATE word list from the Preliminary Study's
  50-word taxonomy -- see pilot_config.py's docstring.
- Descriptor coverage is balanced PER ODORANT SET, not just pooled -- each
  set gets its own running tally (`pick_least_used`, same least-used-first
  rule as the Preliminary Study), so that after ~10 participants, each
  descriptor has been tested roughly equally often *within* each condition,
  not only in aggregate. This matters for a clean A/B comparison: if
  "guava" happened to get tested 8 times under the expert set but only 2
  times under the PCA set, a cluster-level accuracy difference could just
  reflect which specific words got sampled, not a true difference between
  the two odorant sets.
- Block ORDER is counterbalanced by participant sequence position (not by
  parsing participant names): odd-numbered participants (1st, 3rd, 5th...)
  get the expert-chosen set first; even-numbered get the PCA-derived set
  first. This is a straightforward alternating ABAB/BABA counterbalance for
  order effects (fatigue, learsynge/practice effects across the session).
- Each trial has 4 comparison options (2 near + 1 far distractor per
  target, from pilot_config.DISTRACTOR_TABLE -- own table for this
  study's 46-word list, see that file's docstring for how it was built).
  The target is always an AromaGen device composition (using whichever
  odorant set is the block's active condition); one of the 2 near
  distractors is ALSO an AromaGen device composition, the other near
  distractor plus the far distractor are REAL physical objects the
  experimenter sources and presents directly. Which near distractor gets
  which realization is randomized per trial (coin flip -- see
  build_trial() below), not fixed by table position. Presentation order
  of the 4 options is separately shuffled per trial.
"""
import random

from pilot_config import (
    CLUSTERS,
    DISTRACTOR_TABLE,
    ODORANT_SETS,
    TRIALS_PER_BLOCK,
)

SET_IDS = list(ODORANT_SETS.keys())  # ["expert", "pca"]
assert len(SET_IDS) == 2, "this design assumes exactly two odorant-set conditions"


def pick_least_used(cluster, tally, rng):
    """Pick the single least-used descriptor in `cluster` per `tally`,
    ties broken randomly. Mutates `tally` in place (same pattern as the
    Preliminary Study's assignment engine) so repeated calls across
    clusters/blocks/participants keep converging on balanced coverage."""
    candidates = CLUSTERS[cluster][:]
    rng.shuffle(candidates)
    candidates.sort(key=lambda d: tally.get(d, 0))
    picked = candidates[0]
    tally[picked] = tally.get(picked, 0) + 1
    return picked


def block_order_for_participant(seq_index: int):
    """1-indexed sequence position -> (first_set_id, second_set_id).
    Odd position (1st, 3rd, ...) = expert-chosen first; even position
    (2nd, 4th, ...) = PCA-derived first. Independent of whatever name
    string the experimenter actually types in -- pass the running count of
    participants assigned so far (+1), not something parsed from the name,
    so "P1"/"alice"/anything works identically as long as call order is
    the true enrollment order."""
    if seq_index % 2 == 1:
        return ("expert", "pca")
    return ("pca", "expert")


def build_trial(target: str, set_id: str, rng) -> dict:
    near1, near2, far = DISTRACTOR_TABLE[target]

    # Which of the 2 near-distractor words gets realized as the AromaGen
    # composition vs. the real physical object is randomized per trial
    # (was fixed near1->AromaGen, near2->real; now a coin flip each time).
    if rng.random() < 0.5:
        aromagen_near_word, real_near_word = near1, near2
    else:
        aromagen_near_word, real_near_word = near2, near1

    # Unshuffled slot 0 = target, 1 = aromagen-near, 2 = real-near, 3 = real-far
    # -- then shuffled below. correct_slot always tracks the target after
    # shuffling since it's always the AromaGen target reconstruction.
    unshuffled = [
        {"kind": "aromagen_target", "word": target},
        {"kind": "aromagen_near", "word": aromagen_near_word},
        {"kind": "real_near", "word": real_near_word},
        {"kind": "real_far", "word": far},
    ]
    rng.shuffle(unshuffled)
    correct_slot = next(i for i, o in enumerate(unshuffled) if o["kind"] == "aromagen_target")

    return {
        "target": target,
        "cluster": CLUSTERS_LOOKUP[target],
        "odorant_set": set_id,
        "options": unshuffled,  # list of 4 {kind, word}, in presentation order
        "correct_slot": correct_slot,  # 0-indexed position of aromagen_target
    }


CLUSTERS_LOOKUP = {d: c for c, ds in CLUSTERS.items() for d in ds}


def build_block(set_id: str, tally: dict, rng) -> list:
    targets = [pick_least_used(cluster, tally, rng) for cluster in CLUSTERS]
    rng.shuffle(targets)  # randomize trial order within the block
    return [build_trial(t, set_id, rng) for t in targets]


def build_participant_plan(seq_index: int, tallies: dict, seed=None) -> dict:
    """tallies: {"expert": {descriptor: count}, "pca": {descriptor: count}},
    mutated in place -- pass the running tallies from every participant
    assigned so far (real system: computed fresh from the master
    spreadsheet's trials sheet; here: whatever the caller tracked), same
    "continues from the true running total" contract as the Preliminary
    Study's build_assignment()."""
    rng = random.Random(seed)
    first_set, second_set = block_order_for_participant(seq_index)
    return {
        "seq_index": seq_index,
        "block_order": [first_set, second_set],
        "blocks": {
            first_set: build_block(first_set, tallies[first_set], rng),
            second_set: build_block(second_set, tallies[second_set], rng),
        },
    }


def validate_plan(plan: dict):
    """Diagnostics: each block covers all clusters exactly once, no
    repeated target within a block, correct_slot always points at
    aromagen_target."""
    for set_id, trials in plan["blocks"].items():
        assert len(trials) == TRIALS_PER_BLOCK, f"block {set_id} has {len(trials)} trials, expected {TRIALS_PER_BLOCK}"
        clusters_seen = [t["cluster"] for t in trials]
        assert len(clusters_seen) == len(set(clusters_seen)), f"block {set_id} repeats a cluster"
        targets_seen = [t["target"] for t in trials]
        assert len(targets_seen) == len(set(targets_seen)), f"block {set_id} repeats a target"
        for t in trials:
            assert t["options"][t["correct_slot"]]["kind"] == "aromagen_target"
            kinds = sorted(o["kind"] for o in t["options"])
            assert kinds == ["aromagen_near", "aromagen_target", "real_far", "real_near"]


if __name__ == "__main__":
    tallies = {"expert": {}, "pca": {}}
    n_participants = 10
    for i in range(1, n_participants + 1):
        plan = build_participant_plan(i, tallies, seed=1000 + i)
        validate_plan(plan)
        print(f"P{i}: block order = {plan['block_order']}")

    print("\n=== Per-condition descriptor coverage after 10 participants ===")
    for set_id, tally in tallies.items():
        counts = sorted(tally.values())
        print(f"  {set_id}: n_descriptors_covered={len(tally)}, "
              f"min={counts[0]}, max={counts[-1]}, spread={counts[-1] - counts[0]}")

    print("\n=== Block-order counterbalance check ===")
    order_counts = {"expert_first": 0, "pca_first": 0}
    tallies2 = {"expert": {}, "pca": {}}
    for i in range(1, n_participants + 1):
        plan = build_participant_plan(i, tallies2, seed=2000 + i)
        if plan["block_order"][0] == "expert":
            order_counts["expert_first"] += 1
        else:
            order_counts["pca_first"] += 1
    print(f"  {order_counts} (should be 5/5 for 10 participants)")

    print("\n=== Sample single-trial structure ===")
    sample_plan = build_participant_plan(1, {"expert": {}, "pca": {}}, seed=42)
    sample_trial = sample_plan["blocks"][sample_plan["block_order"][0]][0]
    import json
    print(json.dumps(sample_trial, indent=2))
