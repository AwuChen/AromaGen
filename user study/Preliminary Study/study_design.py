"""
Prototype/validation sandbox for the AromaGen User Study 1 assignment engine.
This is NOT what runs the actual study -- it's where the balanced
incomplete-block algorithm gets designed and checked before being ported
1:1 into Apps Script (Code.gs), which is the real, deployed system (Google
Forms live inside Google's ecosystem, so the control panel has to be Apps
Script, not a separate Python backend).

Distractor table (target -> 3 distractors): 2 "near" + 1 "far", per user
spec. The 12 clusters split into two families of 6 for this purpose --
{Floral, Citrus, Woody & Resinous, Herbal & Cooling, Spice, Sweet &
Gourmand} and {Roasted & Smoky, Fermented & Sour, Putrid & Decay, Body &
Animalic, Chemical & Solvent, Perfumed & Clean}. NOTE: this is a DIFFERENT
grouping from PLEASANT_CLUSTERS below (trial presentation order) -- that
one has Spice as not-pleasant and Roasted & Smoky as pleasant; this one has
Spice grouped with the first family and Roasted & Smoky with the second.
The two groupings were specified independently for different purposes,
don't assume they match.

Each cluster has 2 fixed near-neighbors (always same family, a "next two
in a fixed ring" pattern given explicitly by the user per cluster) -- one
distractor drawn from each. The far distractor is drawn from the OTHER
family's 6 clusters, round-robin across every descriptor sharing that far
pool so usage balances evenly across all 6 (verified: 4/4/4/4/4/4 for the
24 second-family descriptors against the first family's 6 clusters;
5/5/4/4/4/4 for the 26 first-family descriptors against the second
family's 6 clusters -- 26 doesn't divide evenly by 6, so spread-of-1 is
the best achievable, same principle as the descriptor-tally balancing
elsewhere in this project), plus a further rotation for which specific
word within the chosen far cluster.
"""
import math
import random

CLUSTERS = {
    "Floral": ["jasmine", "lilac", "rose", "lavender"],
    "Citrus": ["lemony", "currant", "tangy", "guava"],
    "Woody & Resinous": ["sandalwood", "Myrrh", "Cedar", "saffron", "piney"],
    "Herbal & Cooling": ["minty", "wintergreen", "rosemary", "eucalyptus"],
    "Spice": ["anise", "cinnamon", "peppery", "cumin", "nutmeg"],
    "Sweet & Gourmand": ["Honeyed", "Vanilla", "Maple-syrup", "Coconut"],
    "Roasted & Smoky": ["woodsmoke", "fresh_bread", "toasty", "smoky"],
    "Fermented & Sour": ["vinegar-like", "yeasty", "sour_milk", "butyric"],
    "Putrid & Decay": ["rotten-egg", "musty", "rotten_fish", "feces"],
    "Body & Animalic": ["fishy", "wet_dog", "bad_breath", "sweaty"],
    "Chemical & Solvent": ["burnt_rubber", "disinfectant", "chlorine", "nail-polisher"],
    "Perfumed & Clean": ["aftershave", "air_freshener", "perfumer", "skin-care"],
}

# Sniffin' Sticks / UPSIT overrides (per the study protocol's distractor
# rule 1) are NOT applied here -- I don't have a verified, authoritative
# copy of those proprietary item-level answer keys, so this table is the
# fallback-rule (rule 2) distractor set for every descriptor.
DISTRACTOR_TABLE = {
    "jasmine": ["lemony", "sandalwood", "woodsmoke"],
    "lilac": ["currant", "Myrrh", "vinegar-like"],
    "rose": ["tangy", "Cedar", "rotten-egg"],
    "lavender": ["guava", "saffron", "fishy"],
    "lemony": ["sandalwood", "minty", "burnt_rubber"],
    "currant": ["Myrrh", "wintergreen", "aftershave"],
    "tangy": ["Cedar", "rosemary", "fresh_bread"],
    "guava": ["saffron", "eucalyptus", "yeasty"],
    "sandalwood": ["minty", "anise", "musty"],
    "Myrrh": ["wintergreen", "cinnamon", "wet_dog"],
    "Cedar": ["rosemary", "peppery", "disinfectant"],
    "saffron": ["eucalyptus", "cumin", "air_freshener"],
    "piney": ["minty", "nutmeg", "toasty"],
    "minty": ["Honeyed", "anise", "sour_milk"],
    "wintergreen": ["Vanilla", "cinnamon", "rotten_fish"],
    "rosemary": ["Maple-syrup", "peppery", "bad_breath"],
    "eucalyptus": ["Coconut", "cumin", "chlorine"],
    "anise": ["Honeyed", "jasmine", "perfumer"],
    "cinnamon": ["Vanilla", "lilac", "smoky"],
    "peppery": ["Maple-syrup", "rose", "butyric"],
    "cumin": ["Coconut", "lavender", "feces"],
    "nutmeg": ["Honeyed", "jasmine", "sweaty"],
    "Honeyed": ["jasmine", "lemony", "nail-polisher"],
    "Vanilla": ["lilac", "currant", "skin-care"],
    "Maple-syrup": ["rose", "tangy", "woodsmoke"],
    "Coconut": ["lavender", "guava", "vinegar-like"],
    "woodsmoke": ["vinegar-like", "rotten-egg", "jasmine"],
    "fresh_bread": ["yeasty", "musty", "lemony"],
    "toasty": ["sour_milk", "rotten_fish", "sandalwood"],
    "smoky": ["butyric", "feces", "minty"],
    "vinegar-like": ["rotten-egg", "fishy", "anise"],
    "yeasty": ["musty", "wet_dog", "Honeyed"],
    "sour_milk": ["rotten_fish", "bad_breath", "lilac"],
    "butyric": ["feces", "sweaty", "currant"],
    "rotten-egg": ["fishy", "burnt_rubber", "Myrrh"],
    "musty": ["wet_dog", "disinfectant", "wintergreen"],
    "rotten_fish": ["bad_breath", "chlorine", "cinnamon"],
    "feces": ["sweaty", "nail-polisher", "Vanilla"],
    "fishy": ["burnt_rubber", "aftershave", "rose"],
    "wet_dog": ["disinfectant", "air_freshener", "tangy"],
    "bad_breath": ["chlorine", "perfumer", "Cedar"],
    "sweaty": ["nail-polisher", "skin-care", "rosemary"],
    "burnt_rubber": ["aftershave", "woodsmoke", "peppery"],
    "disinfectant": ["air_freshener", "fresh_bread", "Maple-syrup"],
    "chlorine": ["perfumer", "toasty", "lavender"],
    "nail-polisher": ["skin-care", "smoky", "guava"],
    "aftershave": ["woodsmoke", "vinegar-like", "saffron"],
    "air_freshener": ["fresh_bread", "yeasty", "eucalyptus"],
    "perfumer": ["toasty", "sour_milk", "cumin"],
    "skin-care": ["smoky", "butyric", "Coconut"],
}

# Confirmed by user: exactly these 6 clusters play first (order among them
# randomized per participant), the remaining 6 play second (also
# randomized among themselves) -- a hard split, not a smooth gradient.
PLEASANT_CLUSTERS = {"Floral", "Citrus", "Woody & Resinous", "Sweet & Gourmand",
                      "Roasted & Smoky", "Herbal & Cooling"}

DESCRIPTOR_TO_CLUSTER = {d: c for c, ds in CLUSTERS.items() for d in ds}

assert set(DISTRACTOR_TABLE) == set(DESCRIPTOR_TO_CLUSTER), "distractor table must cover exactly the 50 descriptors"
assert sum(len(v) for v in CLUSTERS.values()) == 50


def sample_size_report(evals_per_descriptor=30, buffer=0.15):
    """For each exposure condition (12 or 24), how many participants are
    needed to hit a target number of evaluations per descriptor, and what
    that implies for a fixed realistic pool (e.g. 30 recruited)."""
    total_trials_needed = 50 * evals_per_descriptor
    report = {}
    for n in (12, 24):
        participants_needed = math.ceil(total_trials_needed / n)
        recruit_target = math.ceil(participants_needed * (1 + buffer))
        report[n] = {
            "participants_needed_for_target": participants_needed,
            "recruit_with_buffer": recruit_target,
        }
    return report


def realistic_coverage(n_participants, n_exposures):
    """Given an actual participant count, what evals/descriptor does that
    realistically buy at this exposure condition."""
    return n_participants * n_exposures / 50


def pick_least_used(cluster, r, tally, rng):
    """Picks the r least-used descriptors in a cluster, ties broken
    randomly. Mutates `tally` in place so the next pick (next cluster, next
    participant) sees the updated counts."""
    candidates = CLUSTERS[cluster][:]
    rng.shuffle(candidates)
    candidates.sort(key=lambda d: tally[d])
    picked = candidates[:r]
    for d in picked:
        tally[d] = tally.get(d, 0) + 1
    return picked


def build_assignment(participant_ids, n_exposures, tally, seed=None):
    """Greedy balanced-coverage design: each participant gets
    n_exposures/12 descriptors from every cluster, always picking whichever
    descriptors are CURRENTLY least-used per `tally` (mutated in place as
    this batch runs) -- not a fresh per-call deck. This is what makes
    calling this function multiple times, across separate sessions, still
    converge on globally balanced coverage: pass in the tally computed from
    every participant ever assigned so far (real system: computed fresh
    from the master spreadsheet's form_registry; here: whatever the caller
    tracked), and each new batch continues from the true running total
    rather than starting over blind to prior batches.

    Trial order per participant: all PLEASANT_CLUSTERS trials first
    (shuffled among themselves), then all remaining ("unpleasant") trials
    (shuffled among themselves) -- confirmed design, a hard split."""
    if n_exposures not in (12, 24):
        raise ValueError("n_exposures must be 12 or 24")
    r = n_exposures // 12
    rng = random.Random(seed)

    assignments = {}
    for pid in participant_ids:
        pleasant_trials, unpleasant_trials = [], []
        for cluster in CLUSTERS:
            picks = pick_least_used(cluster, r, tally, rng)
            for target in picks:
                distractors = DISTRACTOR_TABLE[target][:]
                options = distractors + [target]
                rng.shuffle(options)
                trial = {
                    "descriptor": target,
                    "cluster": cluster,
                    "options": options,
                    "correct_index": options.index(target),
                }
                (pleasant_trials if cluster in PLEASANT_CLUSTERS else unpleasant_trials).append(trial)
        rng.shuffle(pleasant_trials)
        rng.shuffle(unpleasant_trials)
        assignments[pid] = pleasant_trials + unpleasant_trials
    return assignments


def validate_assignment(assignments):
    """Diagnostics: per-descriptor coverage counts, per-participant
    duplicate check, per-participant cluster-balance check."""
    from collections import Counter
    coverage = Counter()
    for pid, trials in assignments.items():
        seen = [t["descriptor"] for t in trials]
        assert len(seen) == len(set(seen)), f"{pid} has a repeated descriptor"
        cluster_counts = Counter(t["cluster"] for t in trials)
        n_exposures = len(trials)
        r = n_exposures // 12
        assert all(v == r for v in cluster_counts.values()), f"{pid} cluster imbalance: {cluster_counts}"
        for t in trials:
            coverage[t["descriptor"]] += 1
    return coverage


if __name__ == "__main__":
    print("=== Sample size report (target 30 evals/descriptor) ===")
    for n, r in sample_size_report(evals_per_descriptor=30).items():
        print(f"  n_exposures={n}: need {r['participants_needed_for_target']} participants "
              f"(recruit ~{r['recruit_with_buffer']} with 15% buffer)")

    print("\n=== Realistic coverage at ~30 recruited participants ===")
    for n in (12, 24):
        print(f"  n_exposures={n}: ~{realistic_coverage(30, n):.1f} evals/descriptor")

    for n in (12, 24):
        print(f"\n=== Validating assignment for 30 participants in ONE batch, n_exposures={n} ===")
        pids = [f"P{i+1:03d}" for i in range(30)]
        tally = {d: 0 for d in DESCRIPTOR_TO_CLUSTER}
        assignment = build_assignment(pids, n, tally, seed=42)
        coverage = validate_assignment(assignment)
        counts = sorted(coverage.values())
        print(f"  descriptor coverage: min={counts[0]}, max={counts[-1]}, "
              f"spread={counts[-1]-counts[0]}")
        pleasant_first_ok = all(
            t["cluster"] in PLEASANT_CLUSTERS for t in assignment["P001"][:n // 2]
        ) and all(
            t["cluster"] not in PLEASANT_CLUSTERS for t in assignment["P001"][n // 2:]
        )
        print(f"  pleasant-then-unpleasant ordering holds for P001: {pleasant_first_ok}")

        print(f"=== Same scenario, but as TWO separate batches (4 then 26) -- the "
              f"exact 'generate some now, more later' case ===")
        tally2 = {d: 0 for d in DESCRIPTOR_TO_CLUSTER}
        batch1 = build_assignment(pids[:4], n, tally2, seed=1)
        batch2 = build_assignment(pids[4:], n, tally2, seed=2)  # tally2 carries over
        combined = {**batch1, **batch2}
        coverage2 = validate_assignment(combined)
        counts2 = sorted(coverage2.values())
        print(f"  descriptor coverage across both batches combined: min={counts2[0]}, "
              f"max={counts2[-1]}, spread={counts2[-1]-counts2[0]}")
