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
    "Floral": ["Lavender", "cherry blossom", "jasmine tea", "rose hand cream"],
    "Citrus": ["Orange", "mango", "Lemonade", "Lime soda (Sprite)"],
    "Woody & Resinous": ["Pine", "oak", "Wooden wine barrel", "Incense"],
    "Herbal & Cooling": ["Basil", "Cucumber", "Peppermint tea", "Mint chewing gum"],
    "Spice": ["Ginger", "Black pepper", "Chai latte", "Cinnamon roll"],
    "Sweet & Gourmand": ["Coke", "dark chocolate", "Apple pie", "Sweet popcorn", "Vanilla ice cream"],
    "Roasted & Smoky": ["Coffee", "Bacon", "barbeque ribs", "Hot dog with hot sauce"],
    "Fermented & Sour": ["Greek yogurt", "Pickled cucumber", "Fries with ranch sauce", "Nacho with sour cream"],
    "Putrid & Decay": ["Blue cheese", "durian", "Canned sardines", "Sticky tofu with chilli"],
    "Chemical & Solvent": ["Whiskey", "Tequila", "Mint Fluoride mouthwash", "Lavender nail polish remover"],
    "Perfumed & Clean": ["Aloe vera", "Hand sanitizer", "Mint fluoride toothpaste", "Almond oil shampoo"],
    "Savoury & Umami": ["Soy sauce", "Parmesan cheese", "Garlic", "Seasoned pull pork in bbq sauce", "Salty popcorn"],
}

DESCRIPTOR_TO_CLUSTER = {d: c for c, ds in CLUSTERS.items() for d in ds}
assert sum(len(v) for v in CLUSTERS.values()) == 50

TRIALS_PER_PARTICIPANT = len(CLUSTERS)  # 12 -- one target per cluster, one pass

# --- Distractor design: dynamic, balanced, randomized (not a static table) ---
#
# Same family/ring structure as the Internal Pilot Study (2 families of 6
# clusters, each cluster has 2 fixed near-neighbor CLUSTERS within its
# family), but WHICH WORD gets picked from each relevant cluster is decided
# at runtime, randomly among that cluster's least-used-so-far words, with a
# running distractor-usage tally mutated as trials are built (same
# least-used-first balancing principle used for target selection) -- not a
# fixed per-target lookup table. This is what makes every word in the
# 50-word list appear roughly evenly as a distractor across a whole batch
# of participants, while still varying which specific words get picked for
# any given target from one participant to the next.
#
# Family A (6 clusters, ring order): Floral <-> Sweet & Gourmand <-> Spice
#   <-> Woody & Resinous <-> Herbal & Cooling <-> Citrus <-> (back to Floral)
# Family B (6 clusters, ring order): Chemical & Solvent <-> Perfumed &
#   Clean <-> Roasted & Smoky <-> Savoury & Umami <-> Fermented & Sour <->
#   Putrid & Decay <-> (back to Chemical & Solvent)
FAMILY_A_RING = ["Floral", "Sweet & Gourmand", "Spice", "Woody & Resinous", "Herbal & Cooling", "Citrus"]
FAMILY_B_RING = ["Chemical & Solvent", "Perfumed & Clean", "Roasted & Smoky", "Savoury & Umami", "Fermented & Sour", "Putrid & Decay"]

assert set(FAMILY_A_RING) | set(FAMILY_B_RING) == set(CLUSTERS.keys())
assert len(FAMILY_A_RING) == 6 and len(FAMILY_B_RING) == 6


def _ring_neighbors(ring, cluster):
    i = ring.index(cluster)
    n = len(ring)
    return [ring[(i - 1) % n], ring[(i + 1) % n]]


NEIGHBOR_CLUSTERS = {}
for _c in FAMILY_A_RING:
    NEIGHBOR_CLUSTERS[_c] = _ring_neighbors(FAMILY_A_RING, _c)
for _c in FAMILY_B_RING:
    NEIGHBOR_CLUSTERS[_c] = _ring_neighbors(FAMILY_B_RING, _c)

FAMILY_OF_CLUSTER = {}
for _c in FAMILY_A_RING:
    FAMILY_OF_CLUSTER[_c] = "A"
for _c in FAMILY_B_RING:
    FAMILY_OF_CLUSTER[_c] = "B"

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
