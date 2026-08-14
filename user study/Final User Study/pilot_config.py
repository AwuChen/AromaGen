"""
Shared config for the AromaGen Final User Study.

Single fixed 12-odorant set (no longer an A/B condition -- see
BASE_ODORANT_SET below) used for every participant. Each participant does
ONE pass through all 12 clusters (12 trials total), with a post-trial
feedback sub-flow (freeform vs. rating-scale, counterbalanced across
participants) -- see PilotEngine.gs for the feedback mechanics.

Descriptor taxonomy: 12 clusters, 50 words -- its own list, separate from
both the Preliminary Study's and the Internal Pilot Study's taxonomies
(words differ even where cluster names repeat).
"""

CLUSTERS = {
    "Floral": ["Lavender", "rose", "jasmine tea", "cherry blossom cake"],
    "Citrus": ["Orange", "mango", "Lemonade", "Lime soda (Sprite)"],
    "Woody & Resinous": ["birch", "patchouli", "Whiskey and oak candle", "Incense"],
    "Herbal & Cooling": ["Basil", "Cucumber", "Peppermint tea", "Mint chewing gum"],
    "Spice": ["Ginger", "Black pepper", "chai tea", "Cinnamon roll"],
    "Sweet & Gourmand": ["Coke", "dark chocolate", "Apple pie", "Sweet popcorn", "chocolate and marshmallow-flavored pop tarts"],
    "Roasted & Smoky": ["coffee beans", "Bacon", "korean bbq beef patty", "Hot dog with hot sauce"],
    "Fermented & Sour": ["Greek yogurt", "Pickled cucumber", "Fries with ranch sauce", "Nacho with sour cream"],
    "Putrid & Decay": ["Blue cheese", "durian", "Canned sardines", "Natto beans"],
    "Chemical & Solvent": ["Whiskey", "Tequila", "Mint Fluoride mouthwash", "Lavender nail polish remover"],
    "Perfumed & Clean": ["Aloe vera", "Hand sanitizer", "Mint fluoride toothpaste", "Almond oil shampoo"],
    "Savoury & Umami": ["Soy sauce", "Parmesan cheese", "Garlic", "Seasoned pull pork in bbq sauce", "Salty popcorn"],
}

DESCRIPTOR_TO_CLUSTER = {d: c for c, ds in CLUSTERS.items() for d in ds}
assert sum(len(v) for v in CLUSTERS.values()) == 50

TRIALS_PER_PARTICIPANT = len(CLUSTERS)  # 12 -- one target per cluster, one pass

# --- Distractor design: exclusion-list based (replaced the earlier
# family/ring design entirely -- per explicit instruction). For each TARGET
# cluster, EXCLUDED_CLUSTERS lists which OTHER clusters may NOT supply
# distractors; every cluster not excluded (and not the target's own
# cluster) is eligible. Given verbatim by dictation for 10 of the 12
# clusters; Spice's and Perfumed & Clean's entries were never dictated
# directly but are fully recoverable by symmetry (every pair given was
# confirmed to be mutual: if A excludes B, B excludes A too -- a few pairs
# were dictated one-directionally and were made symmetric per explicit
# confirmation). The target's own cluster is ALWAYS implicitly excluded too
# (not re-stated per cluster below) -- distractors are never drawn from the
# same cluster as the target itself, consistent with every other distractor
# design this project has used (near-neighbor rings, family splits) always
# contrasting DIFFERENT clusters, never the target's own.
#
# WHICH WORD gets picked from each eligible cluster is decided at runtime
# by two layered rules (see pilot_assignment.py's pick_distractors): (1) a
# HARD per-cluster non-repeat cycle -- a word already used as a distractor
# for a given target cluster can't be picked again for that cluster until
# every eligible word has been used once, then it resets; (2) among
# whatever's left, least-used-first against a running GLOBAL
# distractor-usage tally (same balancing principle used for target
# selection), so usage also stays even across all 50 words as distractors,
# not just non-repeating per cluster.
EXCLUDED_CLUSTERS = {
    "Floral": ["Woody & Resinous", "Herbal & Cooling", "Perfumed & Clean"],
    "Citrus": ["Woody & Resinous", "Sweet & Gourmand", "Chemical & Solvent", "Herbal & Cooling"],
    "Woody & Resinous": ["Floral", "Herbal & Cooling", "Spice", "Citrus", "Putrid & Decay", "Chemical & Solvent"],
    "Herbal & Cooling": ["Floral", "Citrus", "Woody & Resinous", "Spice", "Sweet & Gourmand", "Chemical & Solvent"],
    "Spice": ["Woody & Resinous", "Herbal & Cooling", "Sweet & Gourmand"],
    "Sweet & Gourmand": ["Citrus", "Herbal & Cooling", "Spice"],
    "Roasted & Smoky": ["Savoury & Umami", "Fermented & Sour"],
    "Fermented & Sour": ["Roasted & Smoky", "Putrid & Decay", "Savoury & Umami"],
    "Putrid & Decay": ["Fermented & Sour", "Savoury & Umami", "Woody & Resinous"],
    "Chemical & Solvent": ["Perfumed & Clean", "Citrus", "Herbal & Cooling", "Woody & Resinous"],
    "Perfumed & Clean": ["Floral", "Chemical & Solvent"],
    "Savoury & Umami": ["Fermented & Sour", "Roasted & Smoky", "Putrid & Decay"],
}

assert set(EXCLUDED_CLUSTERS.keys()) == set(CLUSTERS.keys())
for _c, _excl in EXCLUDED_CLUSTERS.items():
    for _other in _excl:
        assert _c in EXCLUDED_CLUSTERS[_other], f"{_c} excludes {_other} but not vice versa"


def eligible_distractor_clusters(cluster):
    excluded = EXCLUDED_CLUSTERS.get(cluster, [])
    return [c for c in CLUSTERS if c != cluster and c not in excluded]


def eligible_distractor_words(cluster):
    words = []
    for c in eligible_distractor_clusters(cluster):
        words.extend(CLUSTERS[c])
    return words

# --- The single fixed odorant set (no longer an A/B condition) ---
#
# Given verbatim, matches the current live AromaGen catalog
# (aromagen/cartridge_sets.json) exactly, including Seaweed Accord as the
# stand-in for the umami/savoury class.
BASE_ODORANT_SET = [
    "Benz Sal", "Sandalwood", "Clove Bud", "Lavender", "Orange", "Vanilla",
    "Birch tar oil", "Eucalyptus", "Cognac", "Vinegar", "Isovaleric acid",
    "Seaweed Accord",
]

# category + volatility as given, kept for reference/logging even though
# not directly needed by the assignment logic.
ODORANT_CATEGORY = {
    "Benz Sal": "Perfumed / Clean",
    "Sandalwood": "Woody / Resinous",
    "Clove Bud": "Spice",
    "Lavender": "Floral",
    "Orange": "Citrus",
    "Vanilla": "Sweet / Gourmand",
    "Birch tar oil": "Roasted / Smoky",
    "Eucalyptus": "Herbal / Cooling",
    "Cognac": "Chemical / Solvent",
    "Vinegar": "Fermented / Sour",
    "Isovaleric acid": "Animal / Body",
    "Seaweed Accord": "Umami / Savoury (stand-in)",
}
ODORANT_VOLATILITY = {
    "Benz Sal": 4, "Sandalwood": 4, "Clove Bud": 6, "Lavender": 6,
    "Orange": 8, "Vanilla": 3, "Birch tar oil": 3, "Eucalyptus": 8,
    "Cognac": 8, "Vinegar": 8, "Isovaleric acid": 7, "Seaweed Accord": 5,
}

# Brief sensory description per odorant, shown next to each name on the
# rating-scale feedback screen. Sourced from each odorant's "note" field in
# aromagen/cartridge_sets.json.
ODORANT_DESCRIPTIONS = {
    "Benz Sal": "Sweet, balsamic, soft floral, powdery clean note",
    "Sandalwood": "Woody, creamy, soft, warm, slightly sweet base note",
    "Clove Bud": "Warm, pungent, spicy",
    "Lavender": "Floral, herbaceous-sweet, calming",
    "Orange": "Bright, citrus, sweet, juicy top note",
    "Vanilla": "Sweet, creamy, warm, gourmand",
    "Birch tar oil": "Smoky, tarry, leathery, medicinal-burnt",
    "Eucalyptus": "Cool, medicinal, camphoraceous, fresh herbal top note",
    "Cognac": "Sharp, alcoholic, boozy, solvent-like pungency",
    "Vinegar": "Sour, sharp, acetic, pungent",
    "Isovaleric acid": "Sweaty, cheesy, animalic",
    "Seaweed Accord": "Marine, salty, umami, savoury",
}

# --- Feedback-type condition ---
#
# A counterbalanced condition assigned via participant-sequence parity:
# odd -> freeform, even -> rating_scale.
FEEDBACK_TYPES = {
    "freeform": "Freeform feedback",
    "rating_scale": "Rating-scale feedback",
}
MAX_FEEDBACK_ROUNDS = 5


def feedback_type_for_participant(seq_index: int) -> str:
    """Odd sequence position -> freeform; even -> rating_scale."""
    return "freeform" if seq_index % 2 == 1 else "rating_scale"


if __name__ == "__main__":
    print(f"{sum(len(v) for v in CLUSTERS.values())} descriptors across {len(CLUSTERS)} clusters "
          f"({TRIALS_PER_PARTICIPANT} trials/participant, one pass)")
    print(f"Base odorant set: {len(BASE_ODORANT_SET)} odorants -> {BASE_ODORANT_SET}")
    for i in range(1, 5):
        print(f"  seq {i}: feedback_type={feedback_type_for_participant(i)}")
