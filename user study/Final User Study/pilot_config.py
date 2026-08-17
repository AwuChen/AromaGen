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
    "Floral": ["Lavender", "rose", "jasmine tea", "peony and rose oil shampoo"],
    "Citrus": ["Orange", "mango", "Lemonade", "Lime soda (Sprite)"],
    "Woody & Resinous": ["birch", "patchouli", "Whiskey and oak candle", "Incense"],
    "Herbal & Cooling": ["Basil", "Cucumber", "Peppermint tea", "Mint chewing gum"],
    "Spice": ["Ginger", "Black pepper", "chai tea", "Cinnamon roll"],
    "Sweet & Gourmand": ["Coke", "dark chocolate", "Apple pie", "Sweet popcorn", "chocolate and marshmallow pop tarts"],
    "Roasted & Smoky": ["coffee beans", "Bacon", "korean barbeque beef patty", "Hot dog with hot sauce"],
    "Fermented & Sour": ["Greek yogurt", "Pickled cucumber", "Fries with ranch sauce", "Nacho with sour cream"],
    "Putrid & Decay": ["Blue cheese", "durian", "Canned sardines", "Natto beans"],
    "Chemical & Solvent": ["Whiskey", "Tequila", "Mint Fluoride mouthwash", "Lavender nail polish remover"],
    "Perfumed & Clean": ["Aloe vera", "Hand sanitizer", "Mint fluoride toothpaste", "Almond oil shampoo"],
    "Savoury & Umami": ["Soy sauce", "Parmesan cheese", "Garlic", "Seasoned pull pork in barbeque sauce", "Salty popcorn"],
}

DESCRIPTOR_TO_CLUSTER = {d: c for c, ds in CLUSTERS.items() for d in ds}
assert sum(len(v) for v in CLUSTERS.values()) == 50

TRIALS_PER_PARTICIPANT = len(CLUSTERS)  # 12 -- one target per cluster, one pass

# --- Distractor design: exclusion-list based. For each TARGET cluster,
# EXCLUDED_CLUSTERS lists which OTHER clusters may NOT supply distractors;
# every cluster not excluded (and not the target's own cluster) is
# eligible. Given verbatim by dictation for all 12 clusters (revised list,
# replacing the original 10-of-12 dictation); one pair (Citrus/Spice) was
# given one-directionally (Citrus -> Spice only) and was made symmetric per
# the same "fully symmetric" convention established for the original list.
# The target's own cluster is ALWAYS implicitly excluded too (not re-stated
# per cluster below).
#
# WHICH WORD gets picked from each eligible cluster is decided at runtime
# by THREE layered rules (see pilot_assignment.py's pick_distractors):
# (1) a HARD per-PARTICIPANT non-repeat rule -- a word already used as a
# distractor anywhere in this participant's own session (any trial, any
# cluster) is never reused as a distractor again for that same participant;
# (2) a HARD per-cluster non-repeat cycle, tracked globally across the
# whole study -- a word already used as a distractor for a given target
# cluster can't be picked again for that cluster until every eligible word
# has been used once, then it resets; (3) among whatever's left,
# least-used-first against a running GLOBAL distractor-usage tally (same
# balancing principle used for target selection), so usage also stays even
# across all 50 words as distractors, not just non-repeating.
EXCLUDED_CLUSTERS = {
    "Floral": ["Woody & Resinous", "Herbal & Cooling", "Perfumed & Clean", "Chemical & Solvent"],
    "Citrus": ["Sweet & Gourmand", "Chemical & Solvent", "Herbal & Cooling", "Spice"],
    "Woody & Resinous": ["Floral", "Herbal & Cooling", "Spice", "Perfumed & Clean", "Chemical & Solvent"],
    "Herbal & Cooling": ["Floral", "Citrus", "Woody & Resinous", "Spice", "Chemical & Solvent", "Sweet & Gourmand"],
    "Spice": ["Woody & Resinous", "Herbal & Cooling", "Sweet & Gourmand", "Citrus"],
    "Sweet & Gourmand": ["Citrus", "Herbal & Cooling", "Spice"],
    "Roasted & Smoky": ["Savoury & Umami", "Fermented & Sour"],
    "Fermented & Sour": ["Roasted & Smoky", "Putrid & Decay", "Savoury & Umami"],
    "Putrid & Decay": ["Fermented & Sour", "Savoury & Umami"],
    "Chemical & Solvent": ["Perfumed & Clean", "Citrus", "Herbal & Cooling", "Woody & Resinous", "Floral"],
    "Perfumed & Clean": ["Floral", "Chemical & Solvent", "Woody & Resinous"],
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
# (aromagen/cartridge_sets.json) exactly. 6 of the 12 slots are now
# multi-ingredient blends rather than single raw materials (renamed over
# the course of production tuning) -- kept in sync here so that ratio text
# copied straight off the real AromaGen frontend (which now generates these
# blend names) parses correctly via parseRatioText_/parseRatioTextClient_
# instead of silently falling back to an even split. This is a prospective
# change only: already-collected participants' frozen data still shows
# whatever names were current when they were recorded.
BASE_ODORANT_SET = [
    "Benz Sal", "Sandalwood", "Clove Bud + Cumin", "Lavender + Rose",
    "Orange + Lemon", "Vanilla Sugar + Almond Extract",
    "Birch tar oil + Coffee + Clove Bud", "Eucalyptus", "Cognac", "Vinegar",
    "Isovaleric acid", "Seaweed + Fenugreek + Garlic",
]

# category + volatility as given, kept for reference/logging even though
# not directly needed by the assignment logic.
ODORANT_CATEGORY = {
    "Benz Sal": "Perfumed / Clean",
    "Sandalwood": "Woody / Resinous",
    "Clove Bud + Cumin": "Spice",
    "Lavender + Rose": "Floral",
    "Orange + Lemon": "Citrus",
    "Vanilla Sugar + Almond Extract": "Sweet / Gourmand",
    "Birch tar oil + Coffee + Clove Bud": "Roasted / Smoky",
    "Eucalyptus": "Herbal / Cooling",
    "Cognac": "Chemical / Solvent",
    "Vinegar": "Fermented / Sour",
    "Isovaleric acid": "Animal / Body",
    "Seaweed + Fenugreek + Garlic": "Umami / Savoury",
}
ODORANT_VOLATILITY = {
    "Benz Sal": 4, "Sandalwood": 3, "Clove Bud + Cumin": 6, "Lavender + Rose": 5,
    "Orange + Lemon": 8, "Vanilla Sugar + Almond Extract": 3,
    "Birch tar oil + Coffee + Clove Bud": 4, "Eucalyptus": 8,
    "Cognac": 8, "Vinegar": 8, "Isovaleric acid": 7, "Seaweed + Fenugreek + Garlic": 6,
}

# Brief sensory description per odorant, shown next to each name on the
# feedback screen's reference list. Sourced from each odorant's "note"
# field in aromagen/cartridge_sets.json.
ODORANT_DESCRIPTIONS = {
    "Benz Sal": "Sweet, balsamic, soft floral, powdery clean note",
    "Sandalwood": "Woody, creamy, soft, warm, slightly sweet base note",
    "Clove Bud + Cumin": "Warm spice -- pungent clove combined with earthy, dry, slightly bitter cumin",
    "Lavender + Rose": "Floral bouquet -- calming, herbaceous-sweet lavender and dewy, rosy petal-sweetness",
    "Orange + Lemon": "Bright, citrus, sweet-tart -- juicy orange combined with sharp, zesty lemon",
    "Vanilla Sugar + Almond Extract": "Sweet, creamy gourmand -- warm vanilla-sugar sweetness combined with nutty, marzipan-like almond",
    "Birch tar oil + Coffee + Clove Bud": "Smoky, roasted base -- tarry, leathery birch tar, dark roasted coffee, and warm clove",
    "Eucalyptus": "Cool, medicinal, camphoraceous, fresh herbal top note",
    "Cognac": "Sharp, alcoholic, boozy, solvent-like pungency",
    "Vinegar": "Sour, sharp, acetic, pungent",
    "Isovaleric acid": "Sweaty, cheesy, animalic",
    "Seaweed + Fenugreek + Garlic": "Savoury, marine-umami -- salty seaweed and warm, bittersweet fenugreek, with pungent garlic as an accent",
}

# --- Feedback type ---
#
# Used to be a counterbalanced condition (odd -> freeform, even ->
# rating_scale); rating_scale has been dropped, every participant now gets
# freeform feedback. "rating_scale" is kept in FEEDBACK_TYPES only so label
# lookups for already-collected participants (frozen plan_json from before
# this change) keep resolving correctly -- new plans never assign it.
FEEDBACK_TYPES = {
    "freeform": "Freeform feedback",
    "rating_scale": "Rating-scale feedback",
}
MAX_FEEDBACK_ROUNDS = 5


def feedback_type_for_participant(seq_index: int) -> str:
    """Every participant gets freeform feedback (rating_scale condition
    removed). seq_index is unused now but kept in the signature so callers
    don't need to change."""
    return "freeform"


if __name__ == "__main__":
    print(f"{sum(len(v) for v in CLUSTERS.values())} descriptors across {len(CLUSTERS)} clusters "
          f"({TRIALS_PER_PARTICIPANT} trials/participant, one pass)")
    print(f"Base odorant set: {len(BASE_ODORANT_SET)} odorants -> {BASE_ODORANT_SET}")
    for i in range(1, 5):
        print(f"  seq {i}: feedback_type={feedback_type_for_participant(i)}")
