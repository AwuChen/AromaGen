"""
Shared config for the AromaGen Internal Pilot Study: expert-chosen vs.
PCA-derived 12-odorant sets, A/B tested against each other for overall
accuracy, cluster-level accuracy, and qualitative feedback.

Descriptor taxonomy: 11 clusters, 46 words -- a SEPARATE list from the
Preliminary Study's 50-word/12-cluster taxonomy, explicitly scoped to this
internal pilot only (per instruction: "This is the list you should use
only for internal pilot test"). Notably drops "Body & Animalic" relative
to the Preliminary Study's 12 clusters. Each block draws one descriptor
per cluster (11 clusters -> 11 trials/block), two blocks per participant
(one per odorant-set condition) -> 22 total trials/participant.
"""

CLUSTERS = {
    "Floral": ["honeysuckle", "gardenia", "lily", "magnolia"],
    "Citrus": ["Orange", "mango", "Bergamot", "Lime"],
    "Woody & Resinous": ["Balsam", "Incense", "Patchouli", "amber"],
    "Herbal & Cooling": ["Camphor", "cucumber", "sage", "basil"],
    "Spice": ["ginger", "mustard", "pepper", "Chilli"],
    "Sweet & Gourmand": ["Sweet popcorn", "Almond", "Strawberry", "Chocolate", "Peanut butter"],
    "Roasted & Smoky": ["Coffee", "cigarette", "Barbeque", "bacon"],
    "Fermented & Sour": ["Beewax", "Cheese", "Whiskey", "Pickle", "cider"],
    "Putrid & Decay": ["Guano", "Sulfur fertilizer", "Dead fish", "mud"],
    "Chemical & Solvent": ["acetate", "diesel", "gasoline", "alcohol"],
    "Perfumed & Clean": ["makeup", "sunscreen", "candle", "toothpaste"],
}

# The "(n=NN)" annotations given alongside some cluster headers when this
# list was supplied -- meaning unconfirmed (same situation as the
# Preliminary Study's own CLUSTER_N), stored for traceability only.
CLUSTER_N = {
    "Roasted & Smoky": 24,
    "Putrid & Decay": 39,
    "Chemical & Solvent": 22,
    "Perfumed & Clean": 22,
}

# --- Distractor design, mirroring the Preliminary Study's methodology ---
#
# The Preliminary Study split its 12 clusters into two families of 6 and
# gave each cluster 2 fixed near-neighbor clusters within its own family
# (a "ring" the user specified explicitly), drawing one near-distractor
# word from each neighbor cluster; the far distractor came from the OTHER
# family, round-robin/least-used balanced. No equivalent ring was given for
# THIS list, so the family split + ring below is a PROPOSED analogous
# structure (confirmed with the user before implementing), not something
# they hand-specified word-by-word like the original.
#
# Family A (6 clusters, roughly pleasant/food-adjacent), ring order:
#   Floral <-> Sweet & Gourmand <-> Spice <-> Woody & Resinous <->
#   Herbal & Cooling <-> Citrus <-> (back to Floral)
# Family B (5 clusters, roughly unpleasant/industrial), ring order:
#   Perfumed & Clean <-> Roasted & Smoky <-> Fermented & Sour <->
#   Putrid & Decay <-> Chemical & Solvent <-> (back to Perfumed & Clean)
#
# For each target: near_a = least-used word (so far) in one ring-neighbor
# cluster, near_b = least-used word (so far) in the other ring-neighbor
# cluster (least-used-first balancing, same principle used throughout this
# project -- NOT hand-picked per word); far = least-used word (so far) from
# the OTHER family entirely. Verified: near-distractor usage ranges 1-3
# across all 46 words, far-distractor usage ranges 0-2, no target is its
# own distractor, no duplicate distractors within a trial.
FAMILY_A_RING = ["Floral", "Sweet & Gourmand", "Spice", "Woody & Resinous", "Herbal & Cooling", "Citrus"]
FAMILY_B_RING = ["Perfumed & Clean", "Roasted & Smoky", "Fermented & Sour", "Putrid & Decay", "Chemical & Solvent"]

DISTRACTOR_TABLE = {
    "honeysuckle": ["Orange", "Sweet popcorn", "Coffee"],
    "gardenia": ["mango", "Almond", "cigarette"],
    "lily": ["Bergamot", "Strawberry", "Barbeque"],
    "magnolia": ["Lime", "Chocolate", "bacon"],
    "Sweet popcorn": ["honeysuckle", "ginger", "Beewax"],
    "Almond": ["gardenia", "mustard", "Cheese"],
    "Strawberry": ["lily", "pepper", "Whiskey"],
    "Chocolate": ["magnolia", "Chilli", "Pickle"],
    "Peanut butter": ["honeysuckle", "ginger", "cider"],
    "ginger": ["Peanut butter", "Balsam", "Guano"],
    "mustard": ["Sweet popcorn", "Incense", "Sulfur fertilizer"],
    "pepper": ["Almond", "Patchouli", "Dead fish"],
    "Chilli": ["Strawberry", "amber", "mud"],
    "Balsam": ["mustard", "Camphor", "acetate"],
    "Incense": ["pepper", "cucumber", "diesel"],
    "Patchouli": ["Chilli", "sage", "gasoline"],
    "amber": ["ginger", "basil", "alcohol"],
    "Camphor": ["Balsam", "Orange", "makeup"],
    "cucumber": ["Incense", "mango", "sunscreen"],
    "sage": ["Patchouli", "Bergamot", "candle"],
    "basil": ["amber", "Lime", "toothpaste"],
    "Orange": ["Camphor", "gardenia", "Coffee"],
    "mango": ["cucumber", "lily", "cigarette"],
    "Bergamot": ["sage", "magnolia", "Barbeque"],
    "Lime": ["basil", "honeysuckle", "bacon"],
    "makeup": ["acetate", "Coffee", "honeysuckle"],
    "sunscreen": ["diesel", "cigarette", "gardenia"],
    "candle": ["gasoline", "Barbeque", "lily"],
    "toothpaste": ["alcohol", "bacon", "magnolia"],
    "Coffee": ["makeup", "Beewax", "Orange"],
    "cigarette": ["sunscreen", "Cheese", "mango"],
    "Barbeque": ["candle", "Whiskey", "Bergamot"],
    "bacon": ["toothpaste", "Pickle", "Lime"],
    "Beewax": ["Coffee", "Guano", "Balsam"],
    "Cheese": ["cigarette", "Sulfur fertilizer", "Incense"],
    "Whiskey": ["Barbeque", "Dead fish", "Patchouli"],
    "Pickle": ["bacon", "mud", "amber"],
    "cider": ["Coffee", "Guano", "Camphor"],
    "Guano": ["cider", "acetate", "cucumber"],
    "Sulfur fertilizer": ["Beewax", "diesel", "sage"],
    "Dead fish": ["Cheese", "gasoline", "basil"],
    "mud": ["Whiskey", "alcohol", "ginger"],
    "acetate": ["Sulfur fertilizer", "makeup", "mustard"],
    "diesel": ["Dead fish", "sunscreen", "pepper"],
    "gasoline": ["mud", "candle", "Chilli"],
    "alcohol": ["Guano", "toothpaste", "Sweet popcorn"],
}

# For a DISTRACTOR_TABLE entry [near_a, near_b, far]: the far distractor
# (position 2) is always realized as a real physical object. Which of the
# two near distractors (positions 0/1) becomes the AromaGen composition vs.
# the real physical object is randomized per trial, NOT fixed by position
# -- see build_trial() in pilot_assignment.py.
REAL_FAR_INDEX = 2

DESCRIPTOR_TO_CLUSTER = {d: c for c, ds in CLUSTERS.items() for d in ds}
assert set(DISTRACTOR_TABLE) == set(DESCRIPTOR_TO_CLUSTER), "distractor table must cover exactly the word list"
assert sum(len(v) for v in CLUSTERS.values()) == 46

TRIALS_PER_BLOCK = len(CLUSTERS)  # 11 -- one target per cluster

# --- The two odorant sets under test ---
#
# PCA-DERIVED: per explicit instruction, this is the set currently live in
# the AromaGen system -- see aromagen/cartridge_sets.json. Re-synced
# 2026-08 after a 12th odorant (Seaweed Accord) was added to the live
# catalog -- re-sync again (and cartridge_configs/cartridge_sets_pca.json)
# if the live catalog changes further.
PCA_DERIVED_SET = [
    "Benz Sal", "Sandalwood", "Clove Bud", "Lavender", "Orange", "Vanilla",
    "Birch tar oil", "Eucalyptus", "Cognac", "Vinegar", "Isovaleric acid",
    "Seaweed Accord",
]

# EXPERT-CHOSEN: PLACEHOLDER NAMES -- given verbatim as "A, B, C, D, E, f,
# g, h, i, j, k, l" pending the real 12 expert-chosen odorants.
EXPERT_CHOSEN_SET = ["A", "B", "C", "D", "E", "f", "g", "h", "i", "j", "k", "l"]

# Both sets now have 12 odorants -- the earlier size mismatch (11 vs 12) is
# resolved now that the live PCA-derived catalog has grown to 12.

ODORANT_SETS = {
    "expert": EXPERT_CHOSEN_SET,
    "pca": PCA_DERIVED_SET,
}

ODORANT_SET_LABELS = {
    "expert": "Expert-chosen set",
    "pca": "PCA-derived set (current live AromaGen catalog)",
}


if __name__ == "__main__":
    print(f"{sum(len(v) for v in CLUSTERS.values())} descriptors across {len(CLUSTERS)} clusters "
          f"({TRIALS_PER_BLOCK} trials/block x 2 blocks = {TRIALS_PER_BLOCK * 2} trials/participant)")
    for set_id, names in ODORANT_SETS.items():
        print(f"  {ODORANT_SET_LABELS[set_id]}: {len(names)} odorants -> {names}")
