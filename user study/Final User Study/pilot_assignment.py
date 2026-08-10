"""
Prototype/validation sandbox for the Final User Study's assignment engine
-- same relationship to `apps_script/PilotAssignment.gs` as
`../Preliminary Study/study_design.py` had to that study's `Assignment.gs`.

Design, per the study's current purpose (single fixed odorant set --
overall/cluster-level accuracy is now a one-condition measurement, not an
A/B comparison -- plus qualitative feedback):

- Each PARTICIPANT does ONE PASS of TRIALS_PER_PARTICIPANT trials (= 12,
  one target descriptor per cluster), sampled from the 50-word pool.
  Descriptor coverage is balanced across participants (`pick_least_used`,
  least-used-first), so that after ~10 participants each descriptor has
  been tested roughly equally often.
- FEEDBACK TYPE is a counterbalanced condition, assigned via participant-
  sequence parity: odd -> freeform, even -> rating-scale.
- Each trial has 4 comparison options (2 near + 1 far distractor per
  target). Distractors are chosen DYNAMICALLY at plan-build time, not
  looked up from a fixed table: near distractors = one word from each of
  the target's 2 ring-neighbor clusters (see pilot_config.NEIGHBOR_CLUSTERS),
  far distractor = one word from the other family, each picked as the
  least-used-so-far candidate (random tie-break) against a running
  distractor-usage tally -- same least-used-first balancing principle as
  target selection, so distractor usage stays roughly even across all 50
  words too, not just target usage. The target is always an AromaGen
  device composition; one of the 2 near distractors is ALSO an AromaGen
  device composition (randomized per trial which one), the other near
  distractor plus the far distractor are REAL physical objects. 4-option
  presentation order is separately shuffled per trial.
- The odorant set itself (pilot_config.BASE_ODORANT_SET) is fixed and
  identical for every participant -- no longer a condition to counterbalance
  -- but `odorant_set` is still recorded on every trial/feedback row for
  logging consistency.
"""
import random

from pilot_config import (
    CLUSTERS,
    NEIGHBOR_CLUSTERS,
    FAMILY_OF_CLUSTER,
    BASE_ODORANT_SET,
    TRIALS_PER_PARTICIPANT,
    feedback_type_for_participant,
)

ODORANT_SET_ID = "fixed_set"
CLUSTERS_LOOKUP = {d: c for c, ds in CLUSTERS.items() for d in ds}
ALL_WORDS = [w for c in CLUSTERS for w in CLUSTERS[c]]


def pick_least_used(cluster, tally, rng):
    """Pick the single least-used descriptor in `cluster` per `tally`,
    ties broken randomly. Mutates `tally` in place."""
    candidates = CLUSTERS[cluster][:]
    rng.shuffle(candidates)
    candidates.sort(key=lambda d: tally.get(d, 0))
    picked = candidates[0]
    tally[picked] = tally.get(picked, 0) + 1
    return picked


def pick_least_used_from(words, tally, rng):
    """Same as pick_least_used but over an explicit word list rather than
    a named cluster (used for far-distractor selection across a whole
    family of clusters)."""
    candidates = words[:]
    rng.shuffle(candidates)
    candidates.sort(key=lambda d: tally.get(d, 0))
    picked = candidates[0]
    tally[picked] = tally.get(picked, 0) + 1
    return picked


def pick_distractors(target: str, distractor_tally: dict, rng) -> tuple:
    """Returns (near_a, near_b, far), each dynamically chosen (not a fixed
    table lookup) and balanced against the running distractor_tally."""
    cluster = CLUSTERS_LOOKUP[target]
    neighbor_a, neighbor_b = NEIGHBOR_CLUSTERS[cluster]
    near_a = pick_least_used(neighbor_a, distractor_tally, rng)
    near_b = pick_least_used(neighbor_b, distractor_tally, rng)

    family = FAMILY_OF_CLUSTER[cluster]
    other_family_words = [w for w in ALL_WORDS if FAMILY_OF_CLUSTER[CLUSTERS_LOOKUP[w]] != family]
    far = pick_least_used_from(other_family_words, distractor_tally, rng)

    return near_a, near_b, far


def build_trial(target: str, rng, distractor_tally: dict) -> dict:
    near1, near2, far = pick_distractors(target, distractor_tally, rng)

    # Which of the 2 near-distractor words gets realized as the AromaGen
    # composition vs. the real physical object is randomized per trial.
    if rng.random() < 0.5:
        aromagen_near_word, real_near_word = near1, near2
    else:
        aromagen_near_word, real_near_word = near2, near1

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
        "odorant_set": ODORANT_SET_ID,
        "options": unshuffled,  # list of 4 {kind, word}, in presentation order
        "correct_slot": correct_slot,  # 0-indexed position of aromagen_target
    }


def build_trials(target_tally: dict, distractor_tally: dict, rng) -> list:
    targets = [pick_least_used(cluster, target_tally, rng) for cluster in CLUSTERS]
    rng.shuffle(targets)  # randomize trial order
    return [build_trial(t, rng, distractor_tally) for t in targets]


def build_participant_plan(seq_index: int, target_tally: dict, distractor_tally: dict, seed=None) -> dict:
    """target_tally, distractor_tally: {descriptor: count}, both mutated in
    place -- pass the running tallies from every participant assigned so
    far, same "continues from the true running total" contract as the
    Preliminary Study's build_assignment()."""
    rng = random.Random(seed)
    return {
        "seq_index": seq_index,
        "feedback_type": feedback_type_for_participant(seq_index),
        "odorant_set": ODORANT_SET_ID,
        "trials": build_trials(target_tally, distractor_tally, rng),
    }


def validate_plan(plan: dict):
    """Diagnostics: covers all clusters exactly once, no repeated target,
    correct_slot always points at aromagen_target."""
    trials = plan["trials"]
    assert len(trials) == TRIALS_PER_PARTICIPANT, f"expected {TRIALS_PER_PARTICIPANT} trials, got {len(trials)}"
    clusters_seen = [t["cluster"] for t in trials]
    assert len(clusters_seen) == len(set(clusters_seen)), "repeats a cluster"
    targets_seen = [t["target"] for t in trials]
    assert len(targets_seen) == len(set(targets_seen)), "repeats a target"
    for t in trials:
        assert t["options"][t["correct_slot"]]["kind"] == "aromagen_target"
        kinds = sorted(o["kind"] for o in t["options"])
        assert kinds == ["aromagen_near", "aromagen_target", "real_far", "real_near"]
        words = [o["word"] for o in t["options"]]
        assert t["target"] not in [w for w in words if w != t["target"]] or words.count(t["target"]) == 1
        assert len(set(words)) == 4, f"duplicate word among options: {words}"


if __name__ == "__main__":
    target_tally = {}
    distractor_tally = {}
    n_participants = 10
    for i in range(1, n_participants + 1):
        plan = build_participant_plan(i, target_tally, distractor_tally, seed=1000 + i)
        validate_plan(plan)
        print(f"P{i}: feedback_type={plan['feedback_type']}")

    print("\n=== Target descriptor coverage after 10 participants ===")
    counts = sorted(target_tally.values())
    print(f"  n_descriptors_covered={len(target_tally)}, min={counts[0]}, max={counts[-1]}, spread={counts[-1] - counts[0]}")

    print("\n=== Distractor usage coverage after 10 participants ===")
    dcounts = sorted(distractor_tally.values())
    print(f"  n_words_used_as_distractor={len(distractor_tally)}, min={dcounts[0]}, max={dcounts[-1]}, spread={dcounts[-1] - dcounts[0]}")

    print("\n=== Feedback-type counterbalance check ===")
    fb_counts = {"freeform": 0, "rating_scale": 0}
    target_tally2, distractor_tally2 = {}, {}
    for i in range(1, n_participants + 1):
        plan = build_participant_plan(i, target_tally2, distractor_tally2, seed=2000 + i)
        fb_counts[plan["feedback_type"]] += 1
    print(f"  {fb_counts} (should be 5/5 for 10 participants)")

    print("\n=== Sample single-trial structure ===")
    sample_plan = build_participant_plan(1, {}, {}, seed=42)
    import json
    print(json.dumps(sample_plan["trials"][0], indent=2))
