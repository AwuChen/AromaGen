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
- FEEDBACK TYPE: every participant gets freeform feedback. Used to be a
  counterbalanced condition (odd -> freeform, even -> rating-scale); the
  rating-scale condition has been dropped entirely.
- Each trial has 3 comparison options (2 distractors per target; 3-AFC).
  Distractors are chosen from pilot_config.EXCLUDED_CLUSTERS's eligible
  pool for the target's cluster (every cluster not excluded and not the
  target's own), via two layered rules: (1) a HARD per-cluster non-repeat
  cycle (cluster_used_sets) -- a word already used as a distractor for a
  given target cluster can't be picked again for that cluster until every
  eligible word has been used once, then it resets; (2) among whatever's
  left, least-used-first against a running GLOBAL distractor_tally (same
  balancing principle as target selection), so usage also stays roughly
  even across all 50 words as distractors. The target is always an
  AromaGen device composition; one of the 2 distractors is ALSO an
  AromaGen device composition (randomized per trial which one), the other
  is a REAL physical object. 3-option presentation order is separately
  shuffled per trial.
- The odorant set itself (pilot_config.BASE_ODORANT_SET) is fixed and
  identical for every participant -- no longer a condition to counterbalance
  -- but `odorant_set` is still recorded on every trial/feedback row for
  logging consistency.
"""
import random

from pilot_config import (
    CLUSTERS,
    eligible_distractor_words,
    BASE_ODORANT_SET,
    TRIALS_PER_PARTICIPANT,
    feedback_type_for_participant,
)

ODORANT_SET_ID = "fixed_set"
CLUSTERS_LOOKUP = {d: c for c, ds in CLUSTERS.items() for d in ds}


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
    """Same as pick_least_used but over an explicit word list rather than a
    named cluster (distractor selection's eligible pool spans several
    clusters at once, not just one)."""
    candidates = words[:]
    rng.shuffle(candidates)
    candidates.sort(key=lambda d: tally.get(d, 0))
    picked = candidates[0]
    tally[picked] = tally.get(picked, 0) + 1
    return picked


def pick_distractors(target: str, distractor_tally: dict, rng, cluster_used_sets: dict) -> tuple:
    """Returns (near_a, near_b), 2 DISTINCT words from the target cluster's
    eligible pool (EXCLUDED_CLUSTERS-derived), via two layered rules:

    1. HARD per-cluster non-repeat cycle: cluster_used_sets[cluster] tracks
       every word already used as a distractor for THIS target cluster
       across every participant built so far (mutated in place). A word
       already in that set can't be picked again for this cluster until
       the set is exhausted (fewer than 2 eligible words remain unused),
       at which point it resets and a fresh cycle begins.
    2. Among whatever's left, least-used-first (global distractor_tally,
       random tie-break).
    """
    cluster = CLUSTERS_LOOKUP[target]
    eligible_words = eligible_distractor_words(cluster)
    used_set = cluster_used_sets.setdefault(cluster, set())

    available = [w for w in eligible_words if w not in used_set]
    if len(available) < 2:
        used_set.clear()
        available = eligible_words[:]

    near_a = pick_least_used_from(available, distractor_tally, rng)
    remaining = [w for w in available if w != near_a]
    near_b = pick_least_used_from(remaining, distractor_tally, rng)

    used_set.add(near_a)
    used_set.add(near_b)

    return near_a, near_b


def build_trial(target: str, rng, distractor_tally: dict, cluster_used_sets: dict) -> dict:
    near1, near2 = pick_distractors(target, distractor_tally, rng, cluster_used_sets)

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
    ]
    rng.shuffle(unshuffled)
    correct_slot = next(i for i, o in enumerate(unshuffled) if o["kind"] == "aromagen_target")

    return {
        "target": target,
        "cluster": CLUSTERS_LOOKUP[target],
        "odorant_set": ODORANT_SET_ID,
        "options": unshuffled,  # list of 3 {kind, word}, in presentation order
        "correct_slot": correct_slot,  # 0-indexed position of aromagen_target
    }


def build_trials(target_tally: dict, distractor_tally: dict, rng, cluster_used_sets: dict) -> list:
    targets = [pick_least_used(cluster, target_tally, rng) for cluster in CLUSTERS]
    rng.shuffle(targets)  # randomize trial order
    return [build_trial(t, rng, distractor_tally, cluster_used_sets) for t in targets]


def build_participant_plan(seq_index: int, target_tally: dict, distractor_tally: dict, seed=None,
                            cluster_used_sets: dict = None) -> dict:
    """target_tally, distractor_tally, cluster_used_sets: all mutated in
    place -- pass the running state from every participant assigned so
    far, same "continues from the true running total" contract as the
    Preliminary Study's build_assignment()."""
    rng = random.Random(seed)
    if cluster_used_sets is None:
        cluster_used_sets = {}
    return {
        "seq_index": seq_index,
        "feedback_type": feedback_type_for_participant(seq_index),
        "odorant_set": ODORANT_SET_ID,
        "trials": build_trials(target_tally, distractor_tally, rng, cluster_used_sets),
    }


def validate_plan(plan: dict):
    """Diagnostics: covers all clusters exactly once, no repeated target,
    correct_slot always points at aromagen_target, and both distractors are
    from clusters actually eligible for the target's cluster (never the
    target's own cluster, never an EXCLUDED_CLUSTERS entry)."""
    trials = plan["trials"]
    assert len(trials) == TRIALS_PER_PARTICIPANT, f"expected {TRIALS_PER_PARTICIPANT} trials, got {len(trials)}"
    clusters_seen = [t["cluster"] for t in trials]
    assert len(clusters_seen) == len(set(clusters_seen)), "repeats a cluster"
    targets_seen = [t["target"] for t in trials]
    assert len(targets_seen) == len(set(targets_seen)), "repeats a target"
    for t in trials:
        assert t["options"][t["correct_slot"]]["kind"] == "aromagen_target"
        kinds = sorted(o["kind"] for o in t["options"])
        assert kinds == ["aromagen_near", "aromagen_target", "real_near"]
        words = [o["word"] for o in t["options"]]
        assert t["target"] not in [w for w in words if w != t["target"]] or words.count(t["target"]) == 1
        assert len(set(words)) == 3, f"duplicate word among options: {words}"

        eligible_words = set(eligible_distractor_words(t["cluster"]))
        for o in t["options"]:
            if o["kind"] != "aromagen_target":
                assert o["word"] in eligible_words, \
                    f"distractor {o['word']!r} not eligible for target cluster {t['cluster']!r}"


if __name__ == "__main__":
    target_tally = {}
    distractor_tally = {}
    cluster_used_sets = {}
    n_participants = 10
    seen_distractors_per_cluster = {}  # for the hard-no-repeat-until-exhausted check below
    for i in range(1, n_participants + 1):
        plan = build_participant_plan(i, target_tally, distractor_tally, seed=1000 + i,
                                       cluster_used_sets=cluster_used_sets)
        validate_plan(plan)
        print(f"P{i}: feedback_type={plan['feedback_type']}")
        for t in plan["trials"]:
            distractor_words = [o["word"] for o in t["options"] if o["kind"] != "aromagen_target"]
            prior = seen_distractors_per_cluster.setdefault(t["cluster"], set())
            eligible_count = len(eligible_distractor_words(t["cluster"]))
            repeats = [w for w in distractor_words if w in prior]
            # A repeat is only a violation if the cycle hadn't just reset
            # (i.e. prior wasn't already at/near exhaustion for this cluster).
            if repeats and len(prior) < eligible_count - 1:
                raise AssertionError(
                    f"P{i} cluster {t['cluster']!r}: distractor(s) {repeats} repeated before cycle exhausted "
                    f"({len(prior)}/{eligible_count} used so far)"
                )
            if len(prior) + len(distractor_words) > eligible_count:
                prior.clear()  # cycle reset happened inside build -- mirror it here for tracking
            prior.update(distractor_words)

    print("\n=== Target descriptor coverage after 10 participants ===")
    counts = sorted(target_tally.values())
    print(f"  n_descriptors_covered={len(target_tally)}, min={counts[0]}, max={counts[-1]}, spread={counts[-1] - counts[0]}")

    print("\n=== Distractor usage coverage after 10 participants ===")
    dcounts = sorted(distractor_tally.values())
    print(f"  n_words_used_as_distractor={len(distractor_tally)}, min={dcounts[0]}, max={dcounts[-1]}, spread={dcounts[-1] - dcounts[0]}")

    print("\n=== Hard no-repeat-per-cluster cycle check ===")
    print("  PASSED -- no cluster's distractor pool repeated a word before exhausting all eligible words once")

    print("\n=== Feedback-type check ===")
    fb_counts = {"freeform": 0, "rating_scale": 0}
    target_tally2, distractor_tally2 = {}, {}
    for i in range(1, n_participants + 1):
        plan = build_participant_plan(i, target_tally2, distractor_tally2, seed=2000 + i)
        fb_counts[plan["feedback_type"]] += 1
    assert fb_counts["rating_scale"] == 0, "rating_scale condition should never be assigned anymore"
    print(f"  {fb_counts} (should be {n_participants}/0 -- rating_scale condition removed, freeform only)")

    print("\n=== Sample single-trial structure ===")
    sample_plan = build_participant_plan(1, {}, {}, seed=42)
    import json
    print(json.dumps(sample_plan["trials"][0], indent=2))
