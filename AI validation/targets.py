"""
Target descriptor list for the AromaGen AI validation pipeline
(run_validation.py).

This is the SAME 50-descriptor / 12-cluster taxonomy used in the human
perception study (see `~/Desktop/AromaGen System/data_analysis_users/` and
`~/Desktop/AromaGen/Data Analysis/user_study_1/study_design.py`) -- same
cluster names, same descriptor spellings (including inconsistent
underscore/hyphen usage like "fresh_bread" vs "rotten-egg", kept exactly as
given rather than normalized, so these results stay joinable against the
human-study data by exact descriptor string).

Querying the AI with these same 50 descriptors lets you compare machine
composition behavior directly against how humans performed identifying the
same words from the same taxonomy -- e.g. "is the AI's odorant-set
consistency lower on the clusters where humans also struggled (low
exact/class accuracy), or is it a completely different failure pattern?"

PLEASANTNESS: valence scores as supplied (a negative-is-more-pleasant scale
per the source data -- not independently verified here), where available.
Not every descriptor has one; absent means not provided. Not used by
run_validation.py -- carried along as reference metadata only, in case
stability/reasonableness turns out to correlate with valence.

CLUSTER_N: the "(n=NN)" annotations given alongside some cluster headers.
Left unlabeled what these NN counts refer to (they don't match the n=20
per-cluster accuracy evaluation from the cluster-accuracy dashboard chart,
so likely a different count from the underlying study data) -- stored
as-is for traceability, not interpreted.
"""

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

CLUSTER_N = {
    "Roasted & Smoky": 24,
    "Putrid & Decay": 39,
    "Body & Animalic": 25,
    "Chemical & Solvent": 22,
    "Perfumed & Clean": 22,
}

PLEASANTNESS = {
    "jasmine": -3.65,
    "rose": -4.64,
    "lavender": -4.65,
    "lemony": -2.73,
    "currant": -4.97,
    "tangy": -5.15,
    "guava": -6.10,
    "sandalwood": -4.15,
    "minty": -1.94,
    "wintergreen": -3.04,
    "rosemary": -5.24,
    "eucalyptus": -5.46,
    "anise": -4.76,
    "cinnamon": -4.86,
    "peppery": -5.05,
    "cumin": -5.95,
    "nutmeg": -6.27,
    "woodsmoke": -1.33,
    "fresh_bread": -3.47,
    "toasty": -4.78,
    "vinegar-like": -0.93,
    "yeasty": -2.94,
    "sour_milk": -3.25,
    "butyric": -4.22,
    "rotten-egg": -0.39,
    "musty": -1.64,
    "rotten_fish": -2.63,
    "feces": -6.44,
    "fishy": -2.38,
    "wet_dog": -2.54,
    "bad_breath": -4.41,
    "sweaty": -5.43,
    "burnt_rubber": -0.55,
    "aftershave": -2.87,
    "air_freshener": -3.20,
    "perfumer": -3.46,
    "skin-care": -3.92,
}

# Kept as TARGETS for interface-compatibility with run_validation.py, which
# only needs {category: [target, ...]} -- notes_hint is unused here (no
# targets in this list carry one), unlike the previous ad hoc target set.
TARGETS = CLUSTERS


def flatten_targets():
    """Yields (cluster, descriptor, notes_hint) for every descriptor.
    notes_hint is always None here -- kept for interface compatibility with
    run_validation.py's expectations."""
    for cluster, descriptors in CLUSTERS.items():
        for d in descriptors:
            yield cluster, d, None


if __name__ == "__main__":
    targets = list(flatten_targets())
    print(f"{len(targets)} total targets across {len(CLUSTERS)} clusters")
    for cluster, descriptors in CLUSTERS.items():
        print(f"  {cluster}: {len(descriptors)}")
    assert len(targets) == 50, f"expected 50 descriptors, got {len(targets)}"
