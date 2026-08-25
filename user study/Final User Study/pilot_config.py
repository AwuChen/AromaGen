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


# --- Ratio-source condition ---
#
# A second, independent condition (orthogonal to feedback_type): whether
# the base-odorant ratio shown/used for a target or distractor is the AI's
# own live generation (the existing, only behavior until now) or a fixed
# expert-derived ratio looked up from EXPERT_RATIOS. Chosen once per
# participant at generation time (Admin Panel toggle) and frozen into that
# participant's plan_json -- never retroactive, same prospective-only
# pattern as every other condition in this study.
#
# Unlike feedback_type, this does NOT change trial/target/distractor
# selection at all -- CLUSTERS, EXCLUDED_CLUSTERS, and the balancing logic
# are identical for both conditions. The only difference is an additional
# piece of information (the expert ratio) displayed next to a smell's name
# wherever it's shown -- target or distractor -- when condition == "expert".
CONDITIONS = {
    "ai": "AI-generated ratio",
    "expert": "Expert-derived ratio",
}
DEFAULT_CONDITION = "ai"

# Expert-derived base-odorant ratio per descriptor, keyed by the exact
# descriptor string as it appears in CLUSTERS above. Empty until the real
# 50-word table is provided -- expert_ratio_for() degrades gracefully
# (returns None) for any word not yet in this dict, rather than erroring,
# so the "expert" condition is fully usable (just shows "not yet set") even
# before the table is filled in.
EXPERT_RATIOS = {
    "rose": "Lavender + Rose 50%, Benz Sal 30%, Sandalwood 20%",
    "Lavender": "Eucalyptus 10%, Lavender + Rose 70%, Vanilla Sugar + Almond Extract 20%",
    "peony and rose oil shampoo": "Lavender + Rose 75%, Benz Sal 25%",
    "Orange": "Orange + Lemon 90%, Benz Sal 10%",
    "mango": "Orange + Lemon 25%, Vanilla Sugar + Almond Extract 70%, Benz Sal 5%",
    "Lime soda (Sprite)": "Orange + Lemon 50%, Lavender + Rose 10%, Vanilla Sugar + Almond Extract 20%, Benz Sal 20%",
    "Lemonade": "Orange + Lemon 55%, Vinegar 35%, Vanilla Sugar + Almond Extract 10%",
    "Whiskey and oak candle": "Orange + Lemon 10%, Lavender + Rose 5%, Clove Bud + Cumin 5%, Benz Sal 10%, Vanilla Sugar + Almond Extract 15%, Sandalwood 40%, Birch tar oil + Coffee + Clove Bud 15%",
    "jasmine tea": "Orange + Lemon 10%, Lavender + Rose 35%, Benz Sal 50%, Sandalwood 5%",
    "patchouli": "Benz Sal 50%, Vanilla Sugar + Almond Extract 20%, Sandalwood 20%, Birch tar oil + Coffee + Clove Bud 10%",
    "Incense": "Orange + Lemon 5%, Benz Sal 10%, Seaweed + Fenugreek + Garlic 5%, Sandalwood 60%, Birch tar oil + Coffee + Clove Bud 20%",
    "birch": "Eucalyptus 100%",
    "Cucumber": "Orange + Lemon 20%, Benz Sal 80%",
    "Mint chewing gum": "Eucalyptus 60%, Benz Sal 20%, Vanilla Sugar + Almond Extract 20%",
    "Basil": "Eucalyptus 45%, Orange + Lemon 5%, Lavender + Rose 15%, Seaweed + Fenugreek + Garlic 5%, Sandalwood 25%, Birch tar oil + Coffee + Clove Bud 5%",
    "Peppermint tea": "Eucalyptus 40%, Sandalwood 40%, Birch tar oil + Coffee + Clove Bud 20%",
    "Black pepper": "Orange + Lemon 5%, Clove Bud + Cumin 10%, Seaweed + Fenugreek + Garlic 30%, Sandalwood 20%, Birch tar oil + Coffee + Clove Bud 35%",
    "Ginger": "Orange + Lemon 65%, Clove Bud + Cumin 5%, Vanilla Sugar + Almond Extract 30%",
    "Cinnamon roll": "Clove Bud + Cumin 15%, Vanilla Sugar + Almond Extract 85%",
    "chai tea": "Orange + Lemon 30%, Clove Bud + Cumin 10%, Vanilla Sugar + Almond Extract 30%, Sandalwood 20%, Birch tar oil + Coffee + Clove Bud 10%",
    "Apple pie": "Orange + Lemon 10%, Vanilla Sugar + Almond Extract 80%, Birch tar oil + Coffee + Clove Bud 5%, Benz Sal 5%",
    "Sweet popcorn": "Orange + Lemon 30%, Seaweed + Fenugreek + Garlic 20%, Vanilla Sugar + Almond Extract 50%",
    "dark chocolate": "Orange + Lemon 50%, Vanilla Sugar + Almond Extract 30%, Birch tar oil + Coffee + Clove Bud 20%",
    "chocolate and marshmallow pop tarts": "Orange + Lemon 10%, Vanilla Sugar + Almond Extract 75%, Birch tar oil + Coffee + Clove Bud 5%, Benz Sal 10%",
    "Coke": "Orange + Lemon 30%, Eucalyptus 5%, Vanilla Sugar + Almond Extract 65%",
    "Parmesan cheese": "Seaweed + Fenugreek + Garlic 60%, Isovaleric acid 30%, Birch tar oil + Coffee + Clove Bud 10%",
    "Garlic": "Clove Bud + Cumin 5%, Seaweed + Fenugreek + Garlic 60%, Isovaleric acid 30%, Birch tar oil + Coffee + Clove Bud 5%",
    "Salty popcorn": "Seaweed + Fenugreek + Garlic 30%, Isovaleric acid 40%, Vanilla Sugar + Almond Extract 30%",
    "Seasoned pull pork in barbeque sauce": "Orange + Lemon 10%, Clove Bud + Cumin 10%, Seaweed + Fenugreek + Garlic 55%, Vanilla Sugar + Almond Extract 10%, Birch tar oil + Coffee + Clove Bud 15%",
    "Soy sauce": "Vinegar 30%, Seaweed + Fenugreek + Garlic 50%, Isovaleric acid 10%, Birch tar oil + Coffee + Clove Bud 10%",
    "Almond oil shampoo": "Cognac 5%, Orange + Lemon 20%, Lavender + Rose 5%, Vanilla Sugar + Almond Extract 20%, Benz Sal 50%",
    "Hand sanitizer": "Cognac 30%, Orange + Lemon 10%, Lavender + Rose 10%, Benz Sal 50%",
    "Mint Fluoride mouthwash": "Cognac 10%, Orange + Lemon 10%, Eucalyptus 70%, Vanilla Sugar + Almond Extract 10%",
    "Lavender nail polish remover": "Cognac 40%, Lavender + Rose 60%",
    "Whiskey": "Cognac 80%, Birch tar oil + Coffee + Clove Bud 20%",
    "Tequila": "Cognac 80%, Vanilla Sugar + Almond Extract 20%",
    "Mint fluoride toothpaste": "Eucalyptus 70%, Vanilla Sugar + Almond Extract 30%",
    "Aloe vera": "Cognac 20%, Orange + Lemon 5%, Eucalyptus 5%, Lavender + Rose 10%, Benz Sal 60%",
    "Canned sardines": "Vinegar 5%, Seaweed + Fenugreek + Garlic 45%, Isovaleric acid 30%, Birch tar oil + Coffee + Clove Bud 20%",
    "Blue cheese": "Seaweed + Fenugreek + Garlic 20%, Isovaleric acid 70%, Birch tar oil + Coffee + Clove Bud 10%",
    "Natto beans": "Orange + Lemon 5%, Seaweed + Fenugreek + Garlic 45%, Vinegar 50%",
    "durian": "Orange + Lemon 60%, Isovaleric acid 20%, Vanilla Sugar + Almond Extract 20%",
    "Nacho with sour cream": "Orange + Lemon 5%, Vinegar 45%, Clove Bud + Cumin 5%, Seaweed + Fenugreek + Garlic 35%, Isovaleric acid 10%",
    "Fries with ranch sauce": "Clove Bud + Cumin 10%, Seaweed + Fenugreek + Garlic 70%, Vinegar 20%",
    "Greek yogurt": "Vinegar 70%, Seaweed + Fenugreek + Garlic 5%, Isovaleric acid 25%",
    "Pickled cucumber": "Vinegar 45%, Benz Sal 45%, Vanilla Sugar + Almond Extract 10%",
    "korean barbeque beef patty": "Vinegar 10%, Clove Bud + Cumin 40%, Seaweed + Fenugreek + Garlic 20%, Birch tar oil + Coffee + Clove Bud 30%",
    "Hot dog with hot sauce": "Vinegar 30%, Seaweed + Fenugreek + Garlic 20%, Vanilla Sugar + Almond Extract 30%, Birch tar oil + Coffee + Clove Bud 20%",
    "Bacon": "Seaweed + Fenugreek + Garlic 30%, Vanilla Sugar + Almond Extract 30%, Birch tar oil + Coffee + Clove Bud 40%",
    "coffee beans": "Orange + Lemon 5%, Vanilla Sugar + Almond Extract 50%, Sandalwood 15%, Birch tar oil + Coffee + Clove Bud 30%",
}


def expert_ratio_for(word: str):
    """The expert-derived ratio string for `word`, or None if not yet set
    in EXPERT_RATIOS."""
    return EXPERT_RATIOS.get(word)


if __name__ == "__main__":
    print(f"{sum(len(v) for v in CLUSTERS.values())} descriptors across {len(CLUSTERS)} clusters "
          f"({TRIALS_PER_PARTICIPANT} trials/participant, one pass)")
    print(f"Base odorant set: {len(BASE_ODORANT_SET)} odorants -> {BASE_ODORANT_SET}")
    for i in range(1, 5):
        print(f"  seq {i}: feedback_type={feedback_type_for_participant(i)}")
